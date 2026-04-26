import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Docs - https://docs.streamlit.io/develop/api-reference
# You can have mpre than one page in streamlit - good for if we want to add some kind of "add to t212 pie" feature 

st.title("Stock Comparison Dashboard")
ticker = st.text_input("Please Enter a Ticker to Search:").upper()
st.caption("(one at a time)")
st.write(f"searched for: {ticker}")

st.subheader("Comparison Table")
results_table = pd.DataFrame()
st.write(results_table)

st.subheader("Comparison Chart")