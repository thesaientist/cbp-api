import streamlit as st
import time
import asyncio
from cbp.account.account_mapper import account_data_mapper
# import SessionState

# session = SessionState.get(run_id=0)

# title and interface registration
st.title('Coinbase Pro Positions')
adm = account_data_mapper()

async def main():
    # placeholder
    placeholder = st.empty()
    # Get positions
    while True:
        df = await adm.get_all_positions()
        placeholder.write(df.style.format({'Balance': "{:.2f}", 'Market Price': "{:.2f}", 'Market Value': "{:.2f}", 'Unit Cost': "{:.2f}", 'Cost Basis': "{:.2f}", 'Gain/Loss': "{:.2f}", 'Pct Gain/Loss': "{:.1f}"}))
        time.sleep(5)
        # session.run_id += 1

if __name__ == '__main__':
    asyncio.run(main())
