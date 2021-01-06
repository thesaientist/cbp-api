import streamlit as st
import time
import asyncio
from cbp.account.account_mapper import account_data_mapper
# import SessionState

# session = SessionState.get(run_id=0)

# title and interface registration
st.title('Coinbase Pro Positions')
adm = account_data_mapper()

# format dict
nod = "{:.0f}"
oned = "{:.1f}"
twod = "{:.2f}"
thrd = "{:.3f}"
fmt = {'Balance': twod,
    'Market Price': twod,
    'Market Value': twod,
    'Avg Cost': twod,
    'Cost Basis (CB)': twod,
    'Unrlzd G/L': twod,
    'Pct Unrlzd G/L': oned,
    'Rlzd G/L': twod,
    'Total G/L': twod,
    'Total CB': twod,
    'Pct Total Return': oned,
    'Breakeven Price': thrd
}

async def main():
    # placeholder
    placeholder = st.empty()
    # Get positions
    while True:
        df = await adm.get_all_positions()
        placeholder.write(df.style.format(fmt))
        time.sleep(5)
        # session.run_id += 1

if __name__ == '__main__':
    asyncio.run(main())
