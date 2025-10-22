import hvplot.pandas
import numpy as np
import pandas as pd
import panel as pn

pn.extension()

data = pd.DataFrame([
    ('Monday', 7), ('Tuesday', 4), ('Wednesday', 9), ('Thursday', 4),
    ('Friday', 4), ('Saturday', 5), ('Sunday', 4)], columns=['Day', 'Wind Speed (m/s)']
)

fig = data.hvplot(x="Day", y="Wind Speed (m/s)", line_width=10, ylim=(0,10), title="Wind Speed")

pn.pane.HoloViews(fig, sizing_mode="stretch_width").servable("Forecast Dashboard")