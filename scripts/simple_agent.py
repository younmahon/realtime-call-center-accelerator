import os
import logging
from aiohttp import web
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential

from src.app.backend.azure import get_azure_credentials
from src.app.backend.acs import AcsCaller
from src.app.backend.rtmt import RTMiddleTier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simple_agent")

async def create_app():
    load_dotenv()

    azure_credentials = get_azure_credentials(os.environ.get("AZURE_TENANT_ID"))

    llm_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    llm_deployment = os.environ["AZURE_OPENAI_COMPLETION_DEPLOYMENT_NAME"]
    llm_key = os.environ.get("AZURE_OPENAI_API_KEY")
    llm_credential = azure_credentials if not llm_key else AzureKeyCredential(llm_key)

    rtmt = RTMiddleTier(llm_endpoint, llm_deployment, llm_credential)
    rtmt.system_message = "You are a helpful voice assistant."

    acs_source_number = os.environ["ACS_SOURCE_NUMBER"]
    acs_connection_string = os.environ["ACS_CONNECTION_STRING"]
    acs_callback_path = os.environ["ACS_CALLBACK_PATH"]
    acs_media_streaming_websocket_path = os.environ["ACS_MEDIA_STREAMING_WEBSOCKET_PATH"]

    caller = AcsCaller(
        acs_source_number,
        acs_connection_string,
        acs_callback_path,
        acs_media_streaming_websocket_path,
    )

    async def websocket_handler_acs(request: web.Request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await rtmt.forward_messages(ws, True)
        return ws

    app = web.Application()
    app.router.add_post("/acs/incoming", caller.inbound_call_handler)
    app.router.add_get("/realtime-acs", websocket_handler_acs)

    return app

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8765))
    web.run_app(create_app(), host=host, port=port)
