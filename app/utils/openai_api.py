
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
        self.http_client = aiohttp.ClientSession()

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

        
    async def send_image(self,image_path : str,prompt : str):

        try:
            encoded_image = None
            async with aiofiles.open(image_path,'rb') as f:
                image_data = await f.read()
                encoded_image = base64.b64encode(image_data).decode('utf-8')
            
            if not encoded_image:
                raise HTTPException(status_code=500,
                                    detail="Error encoding image")
            
            headers = {
              "Content-Type": "application/json",
              "Authorization": f"Bearer {self.__API_KEY}"
            }

            payload = {
                  "model": "gpt-4o",
                  "messages": [
                    {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                    {
                      "role": "user",
                      "content": [
                        {
                          "type": "text",
                          "text": f"{prompt}"
                        },
                        {
                          "type": "image_url",
                          "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_image}",
                            "detail": "high"
                          }
                        }
                      ]
                    }
                  ],
                  "max_tokens" : 16384,
                "response_format" : {"type": "json_object" }
                }
            

            async with self.http_client.post(url = "https://api.openai.com/v1/chat/completions", headers=headers, json=payload) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail=f"API request failed with status code {response.status}")
                response_data = await response.json()
                response_data = response_data['choices'][0]['message']['content']
                if response_data == 'NULL':
                    raise HTTPException(status_code=400,
                                        detail="CHASSIS NOT VISIBLE")
              
                response_data = re.sub(r'```json\n|```', '', response_data, flags=re.MULTILINE)

                if isinstance(response_data,str) : 
                    response_data = json.loads(response_data)
                return response_data

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

    async def send_images(self,image_paths : list[str],prompt : str):
        try:
            encoded_images = []
            encoding_task = [image_encoder(image_path) for image_path in image_paths]

            encoded_images = await asyncio.gather(*encoding_task)

            headers = {
              "Content-Type": "application/json",
              "Authorization": f"Bearer {self.__API_KEY}"
            }

            payload = {
                  "model": "gpt-4o",
                  "messages": [
                    {
                      "role": "user",
                      "content": [
                        {
                          "type": "text",
                          "text": f"{prompt}"
                        } 
                      ]
                    }
                  ],
                  "max_tokens" : 16384,

                "response_format" : {"type": "json_object" }
                }
            
            
            image_payloads = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_image}",
                        "detail": "high"
                    }
                }
                for encoded_image in encoded_images
            ]
            payload['messages'][0]['content'].extend(image_payloads)
            
            async with self.http_client.post(url = "https://api.openai.com/v1/chat/completions", headers=headers, json=payload) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail=f"API request failed with status code {response.status}")
                response_data = await response.json()
                response_data = response_data['choices'][0]['message']['content']
                
                return response_data

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