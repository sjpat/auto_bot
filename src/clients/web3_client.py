"""
Web3 Client for Polymarket (Polygon blockchain).

Handles:
- Wallet connection
- USDC balance checks
- Contract approvals
- Transaction signing
"""

import logging
from typing import Optional, Dict, Any
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_typing import Address

logger = logging.getLogger(__name__)


class Web3Client:
    """
    Web3 client for Polymarket blockchain interactions.
    """

    # Polygon RPC endpoints
    POLYGON_RPC = "https://polygon-rpc.com"
    POLYGON_CHAIN_ID = 137

    # Contract addresses
    USDC_CONTRACT = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

    def __init__(
        self,
        private_key: str,
        rpc_url: Optional[str] = None,
        chain_id: int = POLYGON_CHAIN_ID,
    ):
        """
        Initialize Web3 client.

        Args:
            private_key: Wallet private key
            rpc_url: RPC endpoint URL
            chain_id: Chain ID (137 for Polygon mainnet)
        """
        self.logger = logging.getLogger(__name__)

        # Connect to RPC
        self.rpc_url = rpc_url or self.POLYGON_RPC
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))

        # Inject PoA middleware for Polygon
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        self.chain_id = chain_id

        # Load account from private key
        self.account = Account.from_key(private_key)
        self.address = self.account.address

        self.logger.info(f"Web3 client initialized")
        self.logger.info(f"Wallet address: {self.address}")
        self.logger.info(f"Chain ID: {self.chain_id}")
        self.logger.info(f"Connected: {self.w3.is_connected()}")

    def is_connected(self) -> bool:
        """Check if connected to blockchain."""
        return self.w3.is_connected()

    def get_balance(self, address: Optional[str] = None) -> float:
        """
        Get MATIC balance.

        Args:
            address: Wallet address (defaults to client address)

        Returns:
            Balance in MATIC
        """
        address = address or self.address
        balance_wei = self.w3.eth.get_balance(address)
        balance_matic = self.w3.from_wei(balance_wei, "ether")
        return float(balance_matic)

    def get_usdc_balance(self, address: Optional[str] = None) -> float:
        """
        Get USDC balance.

        Args:
            address: Wallet address (defaults to client address)

        Returns:
            Balance in USDC
        """
        address = address or self.address

        # USDC contract ABI (minimal for balanceOf)
        usdc_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            }
        ]

        # Load contract
        usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.USDC_CONTRACT), abi=usdc_abi
        )

        # Get balance (USDC has 6 decimals)
        balance_raw = usdc_contract.functions.balanceOf(
            Web3.to_checksum_address(address)
        ).call()

        balance_usdc = balance_raw / 1e6
        return float(balance_usdc)

    def get_nonce(self, address: Optional[str] = None) -> int:
        """
        Get transaction nonce for address.

        Args:
            address: Wallet address (defaults to client address)

        Returns:
            Current nonce
        """
        address = address or self.address
        return self.w3.eth.get_transaction_count(address)

    def sign_transaction(self, transaction: Dict[str, Any]) -> str:
        """
        Sign transaction with private key.

        Args:
            transaction: Transaction dictionary

        Returns:
            Signed transaction hash
        """
        # Add missing fields
        if "nonce" not in transaction:
            transaction["nonce"] = self.get_nonce()

        if "chainId" not in transaction:
            transaction["chainId"] = self.chain_id

        if "gas" not in transaction:
            transaction["gas"] = 100000  # Default gas limit

        if "gasPrice" not in transaction:
            transaction["gasPrice"] = self.w3.eth.gas_price

        # Sign transaction
        signed_txn = self.w3.eth.account.sign_transaction(
            transaction, private_key=self.account.key
        )

        return signed_txn
