import os, sys, traceback

from token_iq import gateway
from dotenv import load_dotenv


def generate_text():
    try:
        gateway.set_verbose = True
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is this image?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://avatars.githubusercontent.com/u/17561003?v=4"
                        },
                    },
                ],
            }
        ]
        response = gateway.completion(
            model="gemini/gemini-pro-vision",
            messages=messages,
            stop="Hello world",
            num_retries=3,
        )
        print(response)
        assert isinstance(response.choices[0].message.content, str) == True
    except Exception as exception:
        raise Exception("An error occurred during text generation:", exception)


# generate_text()
