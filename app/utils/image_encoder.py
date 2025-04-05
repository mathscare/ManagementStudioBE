import aiofiles
import base64
from fastapi.exceptions import HTTPException

async def image_encoder(image_path : str):
    encoded_image = None
    async with aiofiles.open(image_path,'rb') as f:
                image_data = await f.read()
                encoded_image = base64.b64encode(image_data).decode('utf-8')
            
    if not encoded_image:
        raise HTTPException(status_code=500,
                            detail="Error encoding image")
    return encoded_image