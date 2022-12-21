"""rpc wrapper"""

import secrets
from vxutils import logger


class vxRPCWrapper:
    def __init__(self):
        self._rpc_token = f"rpc_{secrets.token_hex(16)}"
        self._providers = {}

    @property
    def rpc_token(self) -> str:
        return self._rpc_token

    @property
    def methods(self):
        return {method: self.rpc_token for method in self._providers}

    def register(self, provider):
        if not callable(provider):
            for method in dir(provider):
                if method.startswith("_"):
                    continue

                sub_provider = getattr(provider, method)
                if not callable(sub_provider):
                    continue
                self.register(sub_provider)
        else:
            name = (
                provider.__name__
                if hasattr(provider, "__name__")
                else provider.__class__.__name__
            )
            self._providers[name] = provider
            logger.info(f"注册rpc方法: {name} == {provider}")
            return

    def __call__(self, method, *args, **kwargs):
        provider = getattr(self, method)
        return provider(*args, **kwargs)

    def __getattr__(self, method):
        try:
            return self._providers[method]
        except KeyError as e:
            raise AttributeError(f"{method} 未注册...") from e


rpcwrapper = vxRPCWrapper()
