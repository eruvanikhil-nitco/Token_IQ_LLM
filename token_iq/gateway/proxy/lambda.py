from typing import Final

from mangum import Mangum

from token_iq.gateway.proxy.proxy_server import app

handler: Final = Mangum(app, lifespan="on")
