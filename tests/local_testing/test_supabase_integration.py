#### What this tests ####
#    This tests if logging to the supabase integration actually works
import sys, os
import traceback
import pytest

from token_iq import gateway
from token_iq.gateway import embedding, completion

gateway.input_callback = ["supabase"]
gateway.success_callback = ["supabase"]
gateway.failure_callback = ["supabase"]


gateway.set_verbose = False


def test_supabase_logging():
    try:
        response = completion(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello tell me hi"}],
            user="ishaanRegular",
            max_tokens=10,
        )
        print(response)
    except Exception as e:
        print(e)


# test_supabase_logging()


def test_acompletion_sync():
    import asyncio
    import time

    async def completion_call():
        try:
            response = await gateway.acompletion(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "write a poem"}],
                max_tokens=10,
                stream=True,
                user="ishaanStreamingUser",
                timeout=5,
            )
            complete_response = ""
            start_time = time.time()
            async for chunk in response:
                chunk_time = time.time()
                # print(chunk)
                complete_response += chunk["choices"][0]["delta"].get("content", "")
                # print(complete_response)
                # print(f"time since initial request: {chunk_time - start_time:.5f}")

                if chunk["choices"][0].get("finish_reason", None) != None:
                    print("🤗🤗🤗 DONE")
                    return

        except gateway.Timeout as e:
            pass
        except Exception:
            print(f"error occurred: {traceback.format_exc()}")
            pass

    asyncio.run(completion_call())


# test_acompletion_sync()


# reset callbacks
gateway.input_callback = []
gateway.success_callback = []
gateway.failure_callback = []
