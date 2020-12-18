# cbp-api
This is a set of methods to better manage your assets and positions on Coinbase Pro. I created this initially because CBP does not show an overall gain/loss
on each position you've taken, so I decided to use the CBP API to create something for myself.

## Python dependencies
This requires Python 3.x. Python 2.x will NOT work.
You need these following packages installed: `pandas`, `numpy`, `asyncio`, `ssl`, `aiohttp`. Please install them with your `pip` package installer, e.g.

`pip install pandas`

## To install
`git clone https://github.com/thesaientist/cbp-api`

After cloning the repository, add the path to directory `cbp-api` to your PYTHONPATH environment variable. In addition, make sure to set the following environment variables:
* export CBP_API_SECRET=\<set to CBP provided API Secret when API authentication is setup on the CBP website\>
* export CBP_API_KEY=\<set to the CBP provided API key when API authentication is setup on the CBP website\>
* export CBP_API_PASS=\<set to the user provided API password/passphrase when API authentication is setup on the CBP website\>
* export CBP_API_URL=https://api.pro.coinbase.com

These terminal commands will work for UNIX based terminal environments. For Windows, use the appropriate environmental variable setting commands.

API authentication and keys can be setup at https://pro.coinbase.com/profile/api.

A sample notebook is provided with a couple of sample commands, e.g. `get_all_positions()` to P/L of current positions. Please note that all the methods are written in asynchronous syntax, so most methods require
the use of the await keyword. 

