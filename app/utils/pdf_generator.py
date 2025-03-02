import os
import requests
import urllib.parse
from io import BytesIO
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.lib.colors import Color, black, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from app.core.config import Google_maps_key
from pathlib import Path



base_dir = Path(__file__).parent  # directory of the current file
semibold_font_path = base_dir / "fonts" / "Poppins-SemiBold.ttf"
black_font_path = base_dir / "fonts" / "Poppins-SemiBold.ttf"

# Register fonts with corrected file paths
pdfmetrics.registerFont(TTFont("Poppins-SemiBold", str(semibold_font_path)))
pdfmetrics.registerFont(TTFont("Poppins-Regular", str(black_font_path)))

def download_image(url: str) -> BytesIO:
    response = requests.get(url)
    response.raise_for_status()
    return BytesIO(response.content)

def crop_image_to_fit(image_data: BytesIO, target_width: int, target_height: int) -> BytesIO:
    """
    Open the image, center-crop it to match target aspect ratio, then resize using LANCZOS.
    """
    image = Image.open(image_data)
    img_width, img_height = image.size
    target_ratio = target_width / target_height
    img_ratio = img_width / img_height

    if img_ratio > target_ratio:
        new_width = int(img_height * target_ratio)
        left = (img_width - new_width) // 2
        box = (left, 0, left + new_width, img_height)
    else:
        new_height = int(img_width / target_ratio)
        top = (img_height - new_height) // 2
        box = (0, top, img_width, top + new_height)
    cropped = image.crop(box)
    resized = cropped.resize((target_width, target_height), resample=Image.Resampling.LANCZOS)
    out_io = BytesIO()
    resized.save(out_io, format="PNG")
    out_io.seek(0)
    return out_io

def apply_fade_bottom(image_io: BytesIO, fade_height: int = 100) -> BytesIO:
    """
    Applies a fade-out effect at the bottom of the image.
    """
    image = Image.open(image_io).convert("RGBA")
    width, height = image.size

    gradient = Image.new("L", (1, fade_height), color=0xFF)
    for y in range(fade_height):
        alpha = int(255 * (1 - y / fade_height))
        gradient.putpixel((0, y), alpha)
    alpha_gradient = gradient.resize((width, fade_height))
    
    alpha_mask = Image.new("L", (width, height), color=255)
    alpha_mask.paste(alpha_gradient, (0, height - fade_height))
    
    image.putalpha(alpha_mask)
    out_io = BytesIO()
    image.save(out_io, format="PNG")
    out_io.seek(0)
    return out_io

def crop_image_20px(image_data: BytesIO) -> BytesIO:
    """
    Crop 20px from each side of the given image.
    """
    image = Image.open(image_data)
    width, height = image.size
    cropped = image.crop((20, 20, width - 20, height - 20))
    out_io = BytesIO()
    cropped.save(out_io, format="PNG")
    out_io.seek(0)
    return out_io

def apply_rounded_corners(image_data: BytesIO, radius: int = 20) -> BytesIO:
    """
    Apply rounded corners to an image with a specified radius.
    """
    image = Image.open(image_data).convert("RGBA")
    width, height = image.size
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, width, height), radius=radius, fill=255)
    image.putalpha(mask)
    out_io = BytesIO()
    image.save(out_io, format="PNG")
    out_io.seek(0)
    return out_io

def get_static_map(location: str) -> BytesIO:
    """
    Fetch a satellite view static map image from Google Static Maps API.
    """
    api_key = Google_maps_key
    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        "center": location,
        "zoom": "13",
        "size": "600x400",
        "maptype": "satellite",
        "key": api_key,
    }
    query = urllib.parse.urlencode(params)
    url = f"{base_url}?{query}"
    response = requests.get(url)
    response.raise_for_status()
    return BytesIO(response.content)

def get_india_map(location: str) -> BytesIO:
    """
    Fetch a satellite view static map showing the given location on the scale of India.
    """
    api_key = Google_maps_key
    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        "center": "India",
        "zoom": "4",
        "size": "600x400",
        "maptype": "satellite",
        "key": api_key,
        "markers": f"color:red|{location}"
    }
    query = urllib.parse.urlencode(params)
    url = f"{base_url}?{query}"
    response = requests.get(url)
    response.raise_for_status()
    return BytesIO(response.content)

def filter_image_links(attachments: list) -> list:
    allowed_extensions = (".png", ".jpg", ".jpeg", ".gif")
    return [url for url in attachments if url.lower().endswith(allowed_extensions)]

def auto_font_size(text: str, font_name: str, max_width: float, initial_size: int = 36, min_size: int = 12) -> int:
    size = initial_size
    while stringWidth(text, font_name, size) > max_width and size > min_size:
        size -= 1
    return size

detail_style = ParagraphStyle(
    name="DetailStyle",
    fontName="Poppins-Regular",
    fontSize=14,
    leading=18,
    textColor=black,
)

def generate_event_pdf(event: dict, attachments: list, output):
    filtered_attachments = filter_image_links(attachments)
    sorted_attachments = sorted(filtered_attachments) if filtered_attachments else []
    c = canvas.Canvas(output, pagesize=A4)
    page_width, page_height = A4  # approx 595 x 842 pts

    # -------- PAGE 1: Featured Section --------
    featured_area_height = page_height // 2

    if sorted_attachments:
        try:
            featured_url = sorted_attachments[0]
            img_data = download_image(featured_url)
            cropped_img = crop_image_to_fit(img_data, int(page_width), int(featured_area_height))
            faded_img = apply_fade_bottom(cropped_img, fade_height=100)
            featured_image = ImageReader(faded_img)
            c.drawImage(featured_image, 0, page_height - featured_area_height, width=page_width, height=featured_area_height, mask='auto')
        except Exception as e:
            print("Error processing featured image:", e)
    else:
        c.setFillColor(white)
        c.rect(0, page_height - featured_area_height, page_width, featured_area_height, fill=1)

    max_text_width = page_width - 100
    title = event.get("event_name", "Event Name")
    institute = event.get("institute_name", "Institute Name")
    title_font_size = auto_font_size(title, "Poppins-SemiBold", max_text_width, 36, 20)
    institute_font_size = auto_font_size(institute, "Poppins-SemiBold", max_text_width, 24, 16)
    
    title_shadow_offset = max(2, int(title_font_size / 8))
    institute_shadow_offset = max(2, int(institute_font_size / 8))
    
    text_x = 50
    text_y = page_height - 50
    c.setFont("Poppins-SemiBold", title_font_size)
    c.setFillColor(Color(0, 0, 0, alpha=0.6))
    c.drawString(text_x + title_shadow_offset, text_y - title_shadow_offset, title)
    c.setFillColor(white)
    c.drawString(text_x, text_y, title)
    
    c.setFont("Poppins-SemiBold", institute_font_size)
    c.setFillColor(Color(0, 0, 0, alpha=0.6))
    c.drawString(text_x + institute_shadow_offset, text_y - 40 - institute_shadow_offset, institute)
    c.setFillColor(white)
    c.drawString(text_x, text_y - 40, institute)

    # -------- Bottom Half: Maps & Details --------
    bottom_half_height = page_height / 2
    margin = 20
    available_height = bottom_half_height - 3 * margin
    map_height = int(available_height / 2)
    map_width = int(page_width / 2 - 2 * margin)
    
    # Top map: detailed location map
    top_map_x = margin
    top_map_y = bottom_half_height - margin - map_height
    try:
        map_img_io = get_static_map(event.get("location", "New York"))
        map_img_io = crop_image_20px(map_img_io)
        # Round the map image more (radius=20) but draw border with radius=12.
        map_img_io = apply_rounded_corners(map_img_io, radius=20)
        map_image = ImageReader(map_img_io)
        c.drawImage(map_image, top_map_x, top_map_y, width=map_width, height=map_height, mask='auto')
        c.setLineWidth(1)
        c.roundRect(top_map_x, top_map_y, map_width, map_height, radius=12, stroke=1, fill=0)
        loc_text = event.get("location", "New York")
        c.setFont("Poppins-SemiBold", 8)
        wrapped_lines = simpleSplit(loc_text, "Poppins-SemiBold", 8, map_width - 10)
        line_height = 10
        y_line = top_map_y + 5
        for line in wrapped_lines:
            line_w = stringWidth(line, "Poppins-SemiBold", 8)
            c.setFillColor(black)
            c.drawString(top_map_x + map_width - line_w - 5 + 1, y_line - 1, line)
            c.setFillColor(white)
            c.drawString(top_map_x + map_width - line_w - 5, y_line, line)
            y_line += line_height
    except Exception as e:
        print("Error loading top map:", e)
    
    # Bottom map: India-scale map
    bottom_map_x = margin
    bottom_map_y = margin
    try:
        india_map_io = get_india_map(event.get("location", "New York"))
        india_map_io = crop_image_20px(india_map_io)
        india_map_io = apply_rounded_corners(india_map_io, radius=20)
        india_map_image = ImageReader(india_map_io)
        c.drawImage(india_map_image, bottom_map_x, bottom_map_y, width=map_width, height=map_height, mask='auto')
        c.setLineWidth(1)
        c.roundRect(bottom_map_x, bottom_map_y, map_width, map_height, radius=12, stroke=1, fill=0)
        c.setFont("Poppins-SemiBold", 8)
        india_text = "India"
        text_w = stringWidth(india_text, "Poppins-SemiBold", 8)
        c.setFillColor(black)
        c.drawString(bottom_map_x + map_width - text_w - 5 + 1, bottom_map_y + 5 - 1, india_text)
        c.setFillColor(white)
        c.drawString(bottom_map_x + map_width - text_w - 5, bottom_map_y + 5, india_text)
    except Exception as e:
        print("Error loading bottom map:", e)
         
    # Right side: Event details – change event name font color to light blue, no background.
    details_x = page_width / 2 + margin
    details_y = margin
    details_width = page_width / 2 - 2 * margin
    details_height = bottom_half_height - 2 * margin
    details_text = (
        f'<font color="orange" size="20">{event.get("event_name", "")}</font><br/><br/>'
        f'<font color="black" size="16">{event.get("institute_name", "")}</font><br/>'
        f'<font color="black" size="14">{event.get("event_date", "")}</font><br/><br/>'
        f'<font color="black" size="14">{event.get("description", "")}</font><br/><br/>'
        f'<font color="black" size="14">{event.get("location", "")}</font>'
    )
    details_para = Paragraph(details_text, detail_style)
    w, h = details_para.wrap(details_width, details_height)
    details_para.drawOn(c, details_x, details_y + details_height - h)
    
    c.showPage()

    # -------- PAGE 2+: Gallery Layout --------
    gallery_images = sorted_attachments[1:]
    num_images = len(gallery_images)
    index = 0
    while index < num_images:
        remaining = num_images - index
        group_size = 5 if remaining >= 5 else remaining
        group = gallery_images[index:index+group_size]
        
        if group_size == 1:
            try:
                img_io = download_image(group[0])
                cropped = crop_image_to_fit(img_io, int(page_width), int(page_height))
                img_reader = ImageReader(cropped)
                c.drawImage(img_reader, 0, 0, width=page_width, height=page_height, mask='auto')
            except Exception as e:
                c.setFillColor(black)
                c.drawString(50, page_height/2, "Error")
        elif group_size == 2:
            for i in range(2):
                try:
                    img_io = download_image(group[i])
                    cropped = crop_image_to_fit(img_io, int(page_width), int(page_height/2))
                    img_reader = ImageReader(cropped)
                    y_pos = page_height/2 if i == 0 else 0
                    c.drawImage(img_reader, 0, y_pos, width=page_width, height=page_height/2, mask='auto')
                except Exception as e:
                    c.setFillColor(black)
                    c.drawString(50, page_height/2 if i==0 else 50, "Error")
        elif group_size == 3:
            each_h = page_height / 3
            for i in range(3):
                try:
                    img_io = download_image(group[i])
                    cropped = crop_image_to_fit(img_io, int(page_width), int(each_h))
                    img_reader = ImageReader(cropped)
                    y_pos = page_height - (i+1)*each_h
                    c.drawImage(img_reader, 0, y_pos, width=page_width, height=each_h, mask='auto')
                except Exception as e:
                    c.setFillColor(black)
                    c.drawString(50, page_height - (i+1)*each_h + each_h/2, "Error")
        elif group_size == 4:
            each_w = page_width / 2
            each_h = page_height / 2
            positions = [
                (0, each_h),
                (each_w, each_h),
                (0, 0),
                (each_w, 0)
            ]
            for i in range(4):
                try:
                    img_io = download_image(group[i])
                    cropped = crop_image_to_fit(img_io, int(each_w), int(each_h))
                    img_reader = ImageReader(cropped)
                    x, y = positions[i]
                    c.drawImage(img_reader, x, y, width=each_w, height=each_h, mask='auto')
                except Exception as e:
                    c.setFillColor(black)
                    c.drawString(50, 50, "Error")
        elif group_size == 5:
            left_width = 0.6 * page_width
            right_width = 0.4 * page_width
            each_left_h = page_height / 2
            for i in range(2):
                try:
                    img_io = download_image(group[i])
                    cropped = crop_image_to_fit(img_io, int(left_width), int(each_left_h))
                    img_reader = ImageReader(cropped)
                    y_pos = page_height - (i+1)*each_left_h
                    c.drawImage(img_reader, 0, y_pos, width=left_width, height=each_left_h, mask='auto')
                except Exception as e:
                    c.setFillColor(black)
                    c.drawString(50, page_height - (i+1)*each_left_h + each_left_h/2, "Error")
            each_right_h = page_height / 3
            for i in range(3):
                try:
                    img_io = download_image(group[2+i])
                    cropped = crop_image_to_fit(img_io, int(right_width), int(each_right_h))
                    img_reader = ImageReader(cropped)
                    y_pos = page_height - (i+1)*each_right_h
                    c.drawImage(img_reader, left_width, y_pos, width=right_width, height=each_right_h, mask='auto')
                except Exception as e:
                    c.setFillColor(black)
                    c.drawString(left_width + 50, page_height - (i+1)*each_right_h + each_right_h/2, "Error")
        index += group_size
        c.showPage()
        
    c.save()


