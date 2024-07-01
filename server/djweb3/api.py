from djweb3.utils.cli.execution import Execution
from djweb3.utils.models import SingletonAbstract
from djweb3.utils.exception import ConnectionError
from web3 import Web3
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3.middleware.signing import construct_sign_and_send_raw_middleware
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class EthNode(SingletonAbstract):
    w3 = None

    def __init__(self, provider_endpoint=settings.ETH_NODE["address"]):
        assert provider_endpoint is not None, "You must set provider_endpoint"
        EthNode.w3 = Web3(Web3.HTTPProvider(provider_endpoint))
        if not EthNode.w3.is_connected():
            raise ConnectionError()

    @classmethod
    def get_account(cls, private_key):
        assert private_key is not None, "You must set PRIVATE_KEY"
        assert private_key.startswith("0x"), "Private key must start with 0x hex prefix"

        account: LocalAccount = Account.from_key(private_key)
        cls.w3.middleware_onion.add(construct_sign_and_send_raw_middleware(account))

        logger.debug(f"Your hot wallet address is {account.address}")
        return account

    @classmethod
    def create_account(cls):
        account = cls.w3.eth.account.create()
        logger.debug(
            f"private key={cls.w3.to_hex(account.key)}, account={account.address}"
        )
        return account

    @classmethod
    def get_balance(cls, address):
        wei = cls.w3.eth.get_balance(address)
        return cls.w3.from_wei(wei, "ether")
