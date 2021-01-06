import json, hmac, hashlib, time, requests, base64, urllib
import datetime,re, time, math, copy, random
from dateutil import parser
import pandas as pd
import numpy as np
import requests
import asyncio, ssl
import aiohttp

from cbp.common.definitions import CBP_API_URL, CBP_API_SECRET, CBP_API_KEY, CBP_API_PASS

AID_MAP = {
    'BTC': '5f4474c3-0dca-466b-b9f4-63891b77cb0b',
    'ETH': '11d119a5-2a71-4b6f-b54d-708abae22179',
    'LTC': 'd1abac37-685a-40d8-869c-9aada72a97e7',
    'USD': 'c729fb1e-7301-4e7f-9922-8b1e0f5b8853',
    'XRP': '3e90cb8c-97e1-4965-8011-1d1708c76b1c',
    'XLM': '6463e8c4-5cd4-46a7-b0dc-dc36a5fc64d2',
    'EOS': '97c4f9ed-132c-4941-92a2-13162fa96ef5',
    'USDC': '0e494e90-3bf9-459d-b689-c26645ee9682'
}

class account_data_mapper:
    def __init__(self):
        self.auth = True
        self.secret = CBP_API_SECRET
        self.key = CBP_API_KEY
        self.passphrase = CBP_API_PASS
        self.url = CBP_API_URL

    def _get_auth_headers(self, path, method='GET', data='', timestamp=None):
        """Get the headers necessary to authenticate a client request.

        :param str path: The path portion of the REST request. For example,
            '/products/BTC-USD/candles'

        :param str method: (optional) The method of the request. The default is
            GET.

        :param json data: (optional) json-encoded dict or Multidict of key/value
            str pairs to be sent as the body of a POST request. The default is ''.

        :param float timestamp: (optional) A UNIX timestamp. This parameter
            exists for testing purposes and generally should not be used. If a
            timestamp is provided it must be within 30 seconds of the API
            server's time. This can be found using:
            :meth:`copra.rest.Client.server_time`.

        :returns: A dict of headers to be added to the request.

        :raises ValueError: auth is not True.
        """
        if not self.auth:
            raise ValueError('client is not properly configured for authorization')

        if not timestamp:
            timestamp = time.time()
        timestamp = str(timestamp)
        message = timestamp + method + path + data
        message = message.encode('ascii')
        hmac_key = base64.b64decode(self.secret)
        signature = hmac.new(hmac_key, message, hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')

        return {
            'Content-Type': 'Application/JSON',
            'CB-ACCESS-SIGN': signature_b64,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-KEY': self.key,
            'CB-ACCESS-PASSPHRASE': self.passphrase
        }

    async def get(self, path='/', params=None):
        if not params:
            params = {}
        qs = '?{}'.format(urllib.parse.urlencode(params, safe=':')) if params else ''
        url = self.url + path + qs
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_auth_headers(path + qs)) as resp:
                # store the retrieved list of JSON objects in 'data' variable
                data = await resp.json()
        return data

    async def get_account_balances(self):
        path = '/accounts'
        r = await self.get(path)
        accts = pd.DataFrame(r, dtype=float)
        accts = accts[accts.balance != 0.0]
        accts = accts.sort_values(by='available', ascending=False)
        return accts

    async def get_account_history(self, product):
        path = '/accounts/' + AID_MAP[product] + '/ledger'
        try:
            r = await self.get(path)
        except KeyError:
            print('Error: The account ID map does not contain the specific asset key provided as argument! Please check the key is correct and if needed modify the AID map.')
            return
        attempts = 5
        i = 0
        while i < attempts:
            try:
                if i > 0:
                    r = await self.get(path)
                acc_hist = pd.DataFrame(r, dtype=float)
                break
            except ValueError:
                i += 1
                if i < attempts:
                    time.sleep(0.5)
                    continue
                else:
                    raise ValueError(f'There is an issue with accessing this account history! Please check {product} account keys and authorization.')
        if len(acc_hist) != 0:
            acc_hist.loc[:,'created_at'] = pd.to_datetime(acc_hist.created_at)
            return acc_hist
        else:
            print('There is no account history for selected asset on this account.')
            return

    async def get_order_history(self, product):
        path = '/fills'
        params = {'product_id': product+'-USD'}
        r = await self.get(path, params)
        attempts = 5
        i = 0
        while i < attempts:
            try:
                if i > 0:
                    r = await self.get(path, params)
                fills = pd.DataFrame(r)
                break
            except ValueError:
                i += 1
                if i < attempts:
                    time.sleep(0.5)
                    continue
                else:
                    raise ValueError(f'There is an issue with accessing this order history! Please check authorization and that there is an history of fills for this {product}.')
        fills.loc[:,'created_at'] = pd.to_datetime(fills.created_at)
        return fills

    async def get_cost_and_rlzd_gains(self, product):
        hist = await self.get_account_history(product)
        if hist is not None:
            idx = hist.index[hist.balance.astype(np.float) == 0].tolist()
            fills = await self.get_order_history(product)
            if len(idx) == 0:
                lfills = fills
            else:
                last_zero_bal_time = hist.loc[idx[0], 'created_at']
                lfills = fills[fills.created_at > last_zero_bal_time]
            lfills = lfills.sort_values(by='created_at')
            quant = np.array(lfills['size'].astype(np.float) * np.where(lfills['side'] == 'buy', 1, -1))
            if sum(quant) == 0:
                raise ValueError('It looks like your current balance might be 0. Please check your account balance for this asset.')
                return
            rlzd = []
            tot_cost = []
            tot_spent = []
            holding = []
            avg_cost = []
            for i, row in enumerate(lfills.itertuples()):
                if i == 0:
                    if row.side == 'buy':
                        avg_cost.append(float(row.price))
                        holding.append(float(row.size))
                        tot_cost.append(avg_cost[0]*quant[0])
                        rlzd.append(0.)
                        tot_spent.append(tot_cost[0])
                        continue
                    else:
                        raise ValueError('First fill in history is not a buy! Please check order history.')
                p = float(row.price) if row.side == 'buy' else avg_cost[-1]
                q = float(row.size) if row.side == 'buy' else -1.*float(row.size)
                net_gain = -1.*float(row.fee) if row.side == 'buy' else float(row.size)*(float(row.price) - avg_cost[-1])-float(row.fee)
                new_tot_cost = tot_cost[-1] + p*q
                new_holding = holding[-1] + q
                new_avg_cost = new_tot_cost/new_holding
                current_spend = float(row.price) * float(row.size) if row.side == 'buy' else 0.
                rlzd.append(net_gain)
                tot_cost.append(new_tot_cost)
                holding.append(new_holding)
                avg_cost.append(new_avg_cost)
                tot_spent.append(tot_spent[-1] + current_spend)
            # sanity check (latest balance should match last element in holding)
            bal_diff = abs(holding[-1] - hist.iloc[0]['balance'])/hist.iloc[0]['balance']*100
            if bal_diff > 1:        # check if there is more than 1% difference
                raise ValueError('Latest account balance does NOT match calculated latest holdings based on transaction history!')
            return avg_cost[-1], sum(rlzd), tot_spent[-1]
        else:
            print('There is no account history for selected asset on this account.')
            return

    async def get_current_position(self, product):
        # DEBUG
        # print(f'Call to get_current_position() for product {product}')
        accts = await self.get_account_balances()
        if product not in accts.currency.tolist():
            print(f"Error: It looks like you currently don't own any balance of {product}. Please check your account balances.")
            return
        bal = accts.loc[accts.currency == product, 'balance'].astype(np.float).iloc[0]
        avg_cost, rlzd_gains, spend = await self.get_cost_and_rlzd_gains(product)
        price = await self.get_market_price(product)
        position = {
            'Asset': product,
            'Balance': bal,
            'Market Price': price,
            'Market Value': bal*price,
            'Avg Cost': avg_cost,
            'Cost Basis (CB)': bal*avg_cost,
            'Unrlzd G/L': bal*(price-avg_cost),
            'Pct Unrlzd G/L': (price-avg_cost)/avg_cost*100,
            'Rlzd G/L': rlzd_gains,
            'Total G/L': bal*(price-avg_cost)+rlzd_gains,
            'Total CB': spend,
            'Pct Total Return': (bal*(price-avg_cost)+rlzd_gains)/spend*100,
            'Breakeven Price': avg_cost - rlzd_gains/bal
        }
        return position

    async def get_all_positions(self):
        accts = await self.get_account_balances()
        if len(accts) == 0:
            print('Currently, there are no assets on the account.')
            return
        assets = accts[accts.currency != 'USD']['currency'].tolist()
        # assets.remove('USD')
        positions = await asyncio.gather(*[self.get_current_position(asset) for asset in assets])
        # for asset in assets:
        #     pos_rec = self.get_current_position(asset)
        #     positions.append(pos_rec)
        df = pd.DataFrame(positions)
        tot_value = df['Market Value'].sum()
        tot_cost = df['Cost Basis (CB)'].sum()
        tot_unrlzd = df['Unrlzd G/L'].sum()
        tot_rlzd = df['Rlzd G/L'].sum()
        tot_gain = df['Total G/L'].sum()
        tot_CB = df['Total CB'].sum()
        total = {
            'Asset': 'Portfolio',
            # 'Balance': '',
            # 'Market Price': '',
            'Market Value': tot_value,
            # 'Unit Cost': '',
            'Cost Basis (CB)': tot_cost,
            'Unrlzd G/L': tot_unrlzd,
            'Pct Unrlzd G/L': tot_unrlzd/tot_cost*100,
            'Rlzd G/L': tot_rlzd,
            'Total G/L': tot_gain,
            'Total CB': tot_CB,
            'Pct Total Return': tot_gain/tot_CB*100
        }
        df = df.append(total, ignore_index=True)
        return df

    async def get_market_price(self, product):
        path = '/products/' + product + '-USD/ticker'
        r = await self.get(path)
        price = np.float(r['price'])
        return price
