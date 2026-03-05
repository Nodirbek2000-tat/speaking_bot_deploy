from .subscription import SubscriptionMiddleware

def setup(dp):
    dp.middleware.setup(SubscriptionMiddleware())
