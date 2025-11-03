ARG BASE_IMAGE

FROM $BASE_IMAGE

# FROM python:3.10-slim

USER root

RUN pip install folium>=0.14.0 plotly>=5.0.0 tabulator>=1.2.0 trino

USER ${NB_USER}

RUN python3 -m pip list

WORKDIR /app

COPY apps/simulation_dashboard.ipynb simulation_dashboard.ipynb

COPY apps/forecast_dashboard.ipynb forecast_dashboard.ipynb

COPY apps/data_summary_dashboard.ipynb data_summary_dashboard.ipynb

# RUN pip install panel

EXPOSE 5006

CMD [ \
    "panel", \
    "serve", \
    "simulation_dashboard.ipynb", \
    "forecast_dashboard.ipynb", \
    "data_summary_dashboard.ipynb", \
    "--address", "0.0.0.0", \
    "--port", "5006", \
    "--allow-websocket-origin=*", \
    "--log-level", "debug" \
]