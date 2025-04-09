from fastapi import APIRouter, Depends, HTTPException, Body, Query, Response
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime
import base64
import io
from app.schemas.email import EmailData, EmailResponse, Attachment
from app.db.repository.emails import EmailsRepository
from app.core.security import get_current_user
from app.utils.openai_api import gpt
from app.schemas.event import AIEventExtraction
from app.utils.s3 import upload_file_to_s3, get_valid_bucket_name, create_s3_bucket
from fastapi import UploadFile
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()
emails_repo = EmailsRepository()

@router.post("/receive", response_model=Dict[str, Any])
async def receive_email(
    email_data: EmailData = Body(...),
    tenant_id: str = Query(...),
):
    """
    Receive and store an incoming email
    """
    try:
        # Create email record
        email_dict = email_data.dict()
        email_dict["_id"] = str(uuid4())
        email_dict["tenant_id"] = tenant_id
        email_dict["created_at"] = datetime.utcnow()
        email_dict["processed"] = False
        
        # Define bucket name for tenant
        bucket_name = f"AWS_S3_BUCKET_{tenant_id}"
        
        # Ensure bucket exists
        await create_s3_bucket(bucket_name)
        
        # Process attachments if they exist
        if email_dict.get("attachments"):
            for i, attachment in enumerate(email_dict["attachments"]):
                if not attachment.get("filename"):
                    continue
                
                # Get content and decode from base64
                content = attachment.get("content")
                if not content:
                    continue
                
                try:
                    # Decode base64 content
                    file_content = base64.b64decode(content)
                    
                    # Create a file-like object for S3 upload
                    file_obj = io.BytesIO(file_content)
                    
                    # Create upload file object
                    upload_file = UploadFile(
                        filename=attachment["filename"],
                        file=file_obj,
                    )
                    
                    # Generate S3 key
                    attachment_id = str(uuid4())
                    s3_key = f"{tenant_id}/{attachment_id}/{attachment['filename']}"
                    
                    # Upload to S3
                    s3_url = await upload_file_to_s3(upload_file, s3_key, bucket=bucket_name)
                    
                    # Update attachment with S3 information
                    email_dict["attachments"][i]["s3_key"] = s3_key
                    email_dict["attachments"][i]["s3_url"] = s3_url
                    
                    # Remove the base64 content to save database space
                    email_dict["attachments"][i]["content"] = None
                    
                except Exception as e:
                    logger.error(f"Error uploading attachment to S3: {str(e)}")
        
        # Insert into database
        await emails_repo.insert_one(email_dict)
        
        return {
            "success": True,
            "message": "Email received successfully",
            "email_id": str(email_dict["_id"])
        }
    except Exception as e:
        logger.error(f"Error receiving email: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing email: {str(e)}"
        )

@router.get("/", response_model=List[EmailResponse])
async def get_emails(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    sort_field: Optional[str] = Query("created_at", description="Field to sort by"),
    sort_order: Optional[int] = Query(-1, description="Sort order: 1 for ascending, -1 for descending"),
    search: Optional[str] = Query(None, description="Search in subject or from fields"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get a list of emails for the current tenant
    """
    tenant_id = current_user["tenant_id"]
    
    # Build query
    query = {"tenant_id": tenant_id}
    
    # Add search filter if provided
    if search:
        query = {
            "$and": [
                {"tenant_id": tenant_id},
                {"$or": [
                    {"subject": {"$regex": search, "$options": "i"}},
                    {"from_": {"$regex": search, "$options": "i"}}
                ]}
            ]
        }
    
    # Get emails
    emails = await emails_repo.find_many(
        query,
        skip=offset,
        limit=limit,
        sort=[(sort_field, sort_order)]
    )
    
    return emails

@router.get("/{email_id}", response_model=EmailResponse)
async def get_email(
    email_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get a specific email by ID
    """
    tenant_id = current_user["tenant_id"]
    
    # Find email
    email = await emails_repo.find_one({"_id": email_id, "tenant_id": tenant_id})
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    return email

@router.post("/{email_id}/extract-event", response_model=AIEventExtraction)
async def extract_event_from_email(
    email_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Extract event information from a specific email
    """
    tenant_id = current_user["tenant_id"]
    
    # Find email
    email = await emails_repo.find_one({"_id": email_id, "tenant_id": tenant_id})
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    try:
        # Get the email body (plain text preferred, fallback to HTML)
        email_text = email.get("body") if email.get("body") else email.get("html_body")
        
        if not email_text:
            raise HTTPException(
                status_code=400,
                detail="No email body content available for extraction"
            )
        
        # Prepare prompt for AI extraction
        prompt = """
        You are an AI assistant that extracts event information from emails.
        Extract the following fields from the email text:
        - event_name: Name of the event
        - description: Description of the event
        - event_date: Date of the event in YYYY-MM-DD format
        - location: Location where the event will be held
        - institute_name: Name of the institute/organization hosting the event
        - contact_name: Name of the contact person
        - contact_number: Phone number of the contact person
        - email: Email address for contact
        - website: Website of the event or institute (as a valid URL)
        - expected_audience: Expected number of attendees as a number
        - is_paid_event: Whether it's a paid event (true or false)
        - fees: Fee amount if it's a paid event as a number
        - payment_status: Current payment status
        - travel_accomodation: Travel and accommodation details
        - status: Current status of the event planning
        
        For each field, provide the extracted value or null if you can't extract it
        
        Respond with a JSON object that follows the specified schema.
        """
        
        # Add the email subject and text as context
        text = f"Email subject: {email.get('subject')}\nEmail text: {email_text}"        
        ai_extraction = await gpt.send_text(text=text, prompt=prompt, model=AIEventExtraction)
        
        # Mark the email as processed
        await emails_repo.update_one(
            {"_id": email_id},
            {"processed": True, "processed_at": datetime.utcnow()}
        )
        
        return ai_extraction
    except Exception as e:
        logger.error(f"Error extracting event from email: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error extracting event information: {str(e)}"
        )

@router.delete("/{email_id}", response_model=Dict[str, Any])
async def delete_email(
    email_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete a specific email
    """
    tenant_id = current_user["tenant_id"]
    
    # Find and delete email
    email = await emails_repo.find_one({"_id": email_id, "tenant_id": tenant_id})
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    await emails_repo.delete_one({"_id": email_id})
    
    return {"success": True, "message": "Email deleted successfully"}

@router.get("/{email_id}/attachments/{attachment_index}", response_class=Response)
async def get_email_attachment(
    email_id: str,
    attachment_index: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get a specific attachment from an email - redirects to S3 URL
    """
    tenant_id = current_user["tenant_id"]
    
    # Find email
    email = await emails_repo.find_one({"_id": email_id, "tenant_id": tenant_id})
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    attachments = email.get("attachments", [])
    if not attachments or attachment_index >= len(attachments):
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    try:
        attachment = attachments[attachment_index]
        
        # Check if we have an S3 URL
        if attachment.get("s3_url"):
            # Redirect to S3 URL
            return Response(
                status_code=302,
                headers={"Location": attachment["s3_url"]}
            )
        
        # If no S3 URL is available
        raise HTTPException(
            status_code=404, 
            detail="Attachment URL not available"
        )
        
    except Exception as e:
        logger.error(f"Error retrieving attachment: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving attachment: {str(e)}"
        )

@router.post("/{email_id}/create-event", response_model=Dict[str, Any])
async def create_event_from_email(
    email_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Extract event information from an email and create a new event
    """
    tenant_id = current_user["tenant_id"]
    
    # Find email
    email = await emails_repo.find_one({"_id": email_id, "tenant_id": tenant_id})
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    try:
        # First extract event details
        ai_extraction = await extract_event_from_email(email_id, current_user)
        
        # Convert AI extraction to event data format
        # This would typically call the event creation endpoint
        # For simplicity, we'll just mark the email as processed
        
        await emails_repo.update_one(
            {"_id": email_id},
            {"processed": True, "processed_at": datetime.utcnow()}
        )
        
        return {
            "success": True,
            "message": "Event information extracted",
            "extracted_data": ai_extraction
        }
    except Exception as e:
        logger.error(f"Error creating event from email: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating event from email: {str(e)}"
        )
