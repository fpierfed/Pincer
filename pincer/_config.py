# Copyright Pincer 2021-Present
# Full MIT License can be found in `LICENSE` at the project root.

from dataclasses import dataclass


@dataclass
class GatewayConfig:
    """
    This file is to make maintaining the library its gateway
        configuration easier.
    """
    socket_base_url: str = "wss://gateway.discord.gg/"
    version: int = 9
    encoding: str = "json"
    compression: str = "zlib-stream"

    @staticmethod
    def uri() -> str:
        """
        :return uri:
            The GatewayConfig's uri.
        """
        uri = (
            f"{GatewayConfig.socket_base_url}"
            f"?v={GatewayConfig.version}"
            f"&encoding={GatewayConfig.encoding}"
        )

        if GatewayConfig.compressed():
            uri += f"&compress={GatewayConfig.compression}"

        return uri

    @staticmethod
    def compressed() -> bool:
        """
        :return compressed:
            Whether the Gateway should compress payloads or not.
        """
        return GatewayConfig.compression == "zlib-stream"
