"""Shared direct/chat write dispatch; each downstream session gets fresh identity."""


class WritePreparationError(RuntimeError):
    pass


class UserWrites:
    def __init__(self, client, token_factory, request_id):
        self.client = client
        self.token_factory = token_factory
        self.request_id = request_id

    def invoke(self, method, *, idempotency_key, **arguments):
        try:
            token = self.token_factory()
        except Exception:
            raise WritePreparationError("identity_unavailable") from None
        return getattr(self.client, method)(**arguments, access_token=token,
                                           request_id=self.request_id, idempotency_key=idempotency_key)

    def read_watchlist(self):
        return self.client.get_watchlist(access_token=self.token_factory(), request_id=self.request_id)
