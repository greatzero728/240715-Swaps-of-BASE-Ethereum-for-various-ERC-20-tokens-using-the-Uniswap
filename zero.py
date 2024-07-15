import json
from datetime import datetime
from web3 import Web3
from config.config_loader import GrabConfigData, CONFIG_FILE_PATH
from api.cmc_api import get_crypto_price
from api.gas_price import estimate_gas_fee

class WalletManager:
    def __init__(self, base_rpc_url='https://mainnet.base.org'):
        self.config_data = GrabConfigData(CONFIG_FILE_PATH)
        self.config_data.init_master_wallet()
        self.cmc_api_key = self.config_data.get_cmc_api_key()
        self.basew3 = Web3(Web3.HTTPProvider(base_rpc_url))
        self.master_wallet_address = self.config_data.msource_address
        self.master_wallet_private_key = self.config_data.mprivate_key
    
    #################################
    def buy_token(self, from_address, from_private_key, token_address, eth_amount, uniswap_router_address, max_gas_fee_usd=0.01):
        if not self.basew3.is_connected():
            print("Not connected to the BASE network.")
            return

        # Load the Uniswap V2 Router ABI from the file
        with open('abi/UniswapV2.json', 'r') as abi_file:
            uniswap_router_abi = json.load(abi_file)

        uniswap_router_contract = self.basew3.eth.contract(
            address=uniswap_router_address, abi=uniswap_router_abi)

        # Set up the transaction parameters
        nonce = self.basew3.eth.get_transaction_count(from_address)
        gas_limit = 200000

        # Set gas parameters for EIP-1559
        base_fee_gwei = 0.006  # 0.006 Gwei
        max_fee_gwei = 0.008  # 0.008 Gwei
        max_priority_fee_gwei = 0.001  # 0.001 Gwei

        base_fee_wei = self.basew3.to_wei(base_fee_gwei, 'gwei')
        max_fee_wei = self.basew3.to_wei(max_fee_gwei, 'gwei')
        max_priority_fee_wei = self.basew3.to_wei(max_priority_fee_gwei, 'gwei')

        amount_out_min = 0  # Set this according to your minimum acceptable amount out
        deadline = int(datetime.now().timestamp()) + 60 * 10  # 10 minutes from the current time

        # The path is ETH -> Token
        path = [self.basew3.to_checksum_address(from_address), token_address]

        # Build the transaction
        tx = uniswap_router_contract.functions.swapExactETHForTokens(
            amount_out_min,
            path,
            from_address,
            deadline
        ).build_transaction({
            'from': from_address,
            'value': self.basew3.to_wei(eth_amount, 'ether'),
            'gas': gas_limit,
            'maxFeePerGas': max_fee_wei,
            'maxPriorityFeePerGas': max_priority_fee_wei,
            'nonce': nonce,
            'chainId': self.basew3.eth.chain_id
        })

        # Estimate gas fee
        can_proceed, gas_fee_usd = estimate_gas_fee(self.basew3, gas_limit, base_fee_gwei, self.cmc_api_key, max_gas_fee_usd)

        if not can_proceed:
            print(f"Estimated gas fee (${gas_fee_usd:.6f}) exceeds the maximum allowed (${max_gas_fee_usd}).")
            return

        gas_fee_wei = base_fee_wei * gas_limit

        # Fetch the current price of Ethereum using its CoinMarketCap ID
        eth_price = get_crypto_price(1027, self.cmc_api_key)  # CoinMarketCap ID for Ethereum

        total_tx_cost_wei = self.basew3.to_wei(eth_amount, 'ether') + gas_fee_wei
        total_tx_cost_eth = self.basew3.from_wei(total_tx_cost_wei, 'ether')

        # Convert total_tx_cost_eth to float for multiplication
        total_tx_cost_eth_float = float(total_tx_cost_eth)
        total_tx_cost_usd = total_tx_cost_eth_float * eth_price

        # Check the balance of the from_address
        from_balance = self.get_wallet_balance(from_address)
        from_balance_wei = self.basew3.to_wei(from_balance, 'ether')

        print(f"From wallet balance: {from_balance:.18f} ETH")  # 18 decimal places for full precision
        print(f"Amount to transfer: {eth_amount:.18f} ETH")  # 18 decimal places for full precision
        print(f"Amount to transfer (Wei): {self.basew3.to_wei(eth_amount, 'ether')} Wei")
        print(f"Base fee: {base_fee_wei} Wei ({base_fee_gwei} Gwei)")
        print(f"Max fee: {max_fee_wei} Wei ({max_fee_gwei} Gwei)")
        print(f"Max priority fee: {max_priority_fee_wei} Wei ({max_priority_fee_gwei} Gwei)")
        print(f"Gas limit: {gas_limit}")
        print(f"Gas fee (Wei): {gas_fee_wei}")
        print(f"Gas fee (USD): ${gas_fee_usd:.6f}")
        print(f"Total transaction cost (Wei): {total_tx_cost_wei}")
        print(f"Total transaction cost (ETH): {total_tx_cost_eth:.18f} ETH")  # 18 decimal places for full precision
        print(f"Total transaction cost (USD): ${total_tx_cost_usd:.6f}")  # USD conversion

        if total_tx_cost_wei > from_balance_wei:
            print("Insufficient funds for the transaction.")
            return

        # Sign the transaction
        signed_tx = self.basew3.eth.account.sign_transaction(tx, from_private_key)

        # Send the transaction
        tx_hash = self.basew3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"Transaction sent: {tx_hash.hex()}")

        # Wait for the transaction receipt
        receipt = self.basew3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt.status == 1:
            print(f"Transaction successful with hash: {tx_hash.hex()}")
            status = "successful"
        else:
            print(f"Transaction failed with hash: {tx_hash.hex()}")
            status = "failed"

    #################################


# Example usage
if __name__ == "__main__":
    manager = WalletManager()

    # Token address you want to buy (replace with the actual token address)
    token_address = '0x3f07AA85254e396Ca98febb86DeD26A4a85eaff3'

    # Uniswap router address (replace with the actual Uniswap router address on the Base network)
    uniswap_router_address = '0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD'

    # Amount of ETH to spend
    eth_amount = 0.0001  # For example, 0.01 ETH

    # Buy the token
    manager.buy_token(wallet_address, wallet_private_key, token_address, eth_amount, uniswap_router_address)
