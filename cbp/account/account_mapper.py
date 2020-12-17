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
        acc_hist = pd.DataFrame(r, dtype=float)
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
        fills = pd.DataFrame(r)
        fills.loc[:,'created_at'] = pd.to_datetime(fills.created_at)
        return fills

    async def get_avg_cost(self, product):
        hist = await self.get_account_history(product)
        if hist is not None:
            idx = hist.index[hist.balance.astype(np.float) == 0].tolist()
            fills = await self.get_order_history(product)
            if len(idx) == 0:
                lfills = fills
            else:
                last_zero_bal_time = hist.loc[idx[0], 'created_at']
                lfills = fills[fills.created_at > last_zero_bal_time]
            q = np.array(lfills['size'].astype(np.float) * np.where(lfills['side'] == 'buy', 1, -1))
            p = np.array(lfills.price.astype(np.float))
            try:
                vwap = np.average(p, weights=q)
                return vwap
            except ZeroDivisionError:
                print('Error: It looks like your current balance might be 0. Please check your account balance for this asset.')
                return
        else:
            print('There is no account history for selected asset on this account.')
            return

    async def get_current_position(self, product):
        accts = await self.get_account_balances()
        if product not in accts.currency.tolist():
            print(f"Error: It looks like you currently don't own any balance of {product}. Please check your account balances.")
            return
        bal = accts.loc[accts.currency == product, 'balance'].astype(np.float).iloc[0]
        vwap = await self.get_avg_cost(product)
        price = await self.get_market_price(product)
        position = {
            'Asset': product,
            'Balance': bal,
            'Market Price': price,
            'Market Value': bal*price,
            'Unit Cost': vwap,
            'Cost Basis': bal*vwap,
            'Gain/Loss': bal*(price-vwap),
            'Pct Gain/Loss': (price-vwap)/vwap*100
        }
        return position

    async def get_all_positions(self):
        accts = await self.get_account_balances()
        if len(accts) == 0:
            print('Currently, there are no assets on the account.')
            return
        assets = accts.currency.tolist()
        assets.remove('USD')
        positions = await asyncio.gather(*[self.get_current_position(asset) for asset in assets])
        # for asset in assets:
        #     pos_rec = self.get_current_position(asset)
        #     positions.append(pos_rec)
        df = pd.DataFrame(positions)
        tot_value = df['Market Value'].sum()
        tot_cost = df['Cost Basis'].sum()
        net_gain = df['Gain/Loss'].sum()
        total = {
            'Asset': 'Total Portfolio',
            'Balance': '',
            'Market Price': '',
            'Market Value': tot_value,
            'Unit Cost': '',
            'Cost Basis': tot_cost,
            'Gain/Loss': net_gain,
            'Pct Gain/Loss': net_gain/tot_cost*100
        }
        df = df.append(total, ignore_index=True)
        return df

    async def get_market_price(self, product):
        path = '/products/' + product + '-USD/ticker'
        r = await self.get(path)
        price = np.float(r['price'])
        return price
