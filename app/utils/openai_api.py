
import json
from fastapi import HTTPException
from app.core.config import OPENAI_API_KEY
import json
import aiohttp
import re
import aiofiles
import base64
import asyncio
from openai import AsyncOpenAI
from fastapi.exceptions import HTTPException
from app.utils.image_encoder import image_encoder
from pathlib import Path
from pydantic import BaseModel

class GPT():
    def __init__(self,API_KEY : str,model : str,voice_model : str):
        self.client = AsyncOpenAI(api_key=API_KEY)
        self.model = model
        self.__API_KEY = API_KEY
        self.voice_model = voice_model
        self.http_client = None  # Will initialize later

    async def get_http_client(self):
        if self.http_client is None or self.http_client.closed:
            self.http_client = aiohttp.ClientSession()
        return self.http_client

    async def send_text(self,text : str,prompt : str, model : BaseModel = None):
        try:
            response = await self.client.beta.chat.completions.parse(
            messages=[
                {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                {
                    "role": "user",
                    "content": f"{prompt}.text - {text}",
                }
            ],
            model=self.model,
            max_tokens=16384,
            response_format=model if model else {"type": "json_object" }
            )
        except Exception as e:
            print(e)
            raise HTTPException(status_code=500,detail=str(e))
        response = response.to_dict()

        return json.loads(response['choices'][0]['message']['content'])

        
    async def send_image(self, image_path: str, prompt: str,response_model:BaseModel = None):

        try:
            encoded_image = None
            async with aiofiles.open(image_path, "rb") as f:
                image_data = await f.read()
                encoded_image = base64.b64encode(image_data).decode("utf-8")

            if not encoded_image:
                raise HTTPException(status_code=500, detail="Error encoding image")

            response_data = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant designed to output JSON.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{prompt}"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
                max_tokens=16384,
                response_format=response_model if response_model else {"type": "json_object"},
            )

            response_data = response_data.to_dict()
            return json.loads(response_data["choices"][0]["message"]["content"])

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

    async def send_images(self, image_paths: list[str], prompt: str, response_model:BaseModel = None):
        try:
            encoded_images = []
            encoding_task = [image_encoder(image_path) for image_path in image_paths]

            encoded_images = await asyncio.gather(*encoding_task)
            content = [{"type": "text", "text": f"{prompt}"}]

            for encoded_image in encoded_images:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_image}",
                            "detail": "high",
                        },
                    }
                )

            response_data = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[{"role": "user", "content": content}],
                response_format= response_model if response_model else {"type": "json_object"},
            )

            response_data = response_data.to_dict()
            return response_data["choices"][0]["message"]["content"]

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
        
    async def voice_to_text(self,file_path : str):

        try:

                transcription = await self.client.audio.transcriptions.create(
                              model=self.voice_model, 
                              file=Path(file_path),
                              response_format="json"
                            )
        except Exception as e:
                print(e)
                raise HTTPException(status_code=400,detail=str(e))
        
        return transcription

    async def voice_to_text_new(self, prompt: str, encoded_data: str):
      completion = await self.client.chat.completions.create(
        model=self.voice_model,
        messages=[
              {
                  "role": "user",
                  "content": [
                      { 
                          "type": "text",
                          "text": f"{prompt}"
                      },
                      {
                          "type": "input_audio",
                          "input_audio": {
                              "data": encoded_data,
                              "format": "wav"
                          }
                      }
                  ]
              },
        ],
      )
  
      response =  completion.choices[0].message.content
      cleaned_response = re.sub(r'```json\n|\n```', '', response).strip()
      data = json.loads(cleaned_response)
      return data
        
            

gpt = GPT(OPENAI_API_KEY,"gpt-4o-mini","whisper-1")