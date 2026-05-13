# Value Stream — AI E-commerce Intelligence Tool

Value Stream is an AI-powered decision-support dashboard for e-commerce teams. It combines Amazon bestseller trends, Shopify inventory data, and LLM-generated recommendations to help businesses identify product opportunities, respond to market signals, and make faster merchandising decisions.

## Overview

The project was designed for a beauty and skincare store that wanted better visibility into fast-moving market trends. Instead of manually checking bestseller lists and comparing them against stock, Value Stream automates the data flow and presents clear recommendations through a Streamlit dashboard.

The system tracks Amazon bestseller ranking changes, compares those trends with Shopify stock data, and uses an LLM layer to suggest commercial actions such as promotions, hero banners, and product opportunities.

## Key Features

- Automated Amazon bestseller data collection
- Daily trend tracking and ranking change analysis
- Shopify inventory integration
- LLM-generated business recommendations
- Trending unstocked product discovery
- Streamlit dashboard deployed on GCP

## Tech Stack

- Python
- Streamlit
- Google Cloud Platform
- Cloud Scheduler
- Cloud Run
- Cloud SQL
- ScraperAPI
- Shopify API
- LLM integration

## Implementation Highlights

- Built the GCP data pipeline using Cloud Scheduler, Cloud Run, ScraperAPI, and Cloud SQL
- Processed Amazon bestseller data to track ranking changes and trend signals
- Integrated Shopify stock data into the recommendation workflow
- Contributed to the LLM recommendation layer
- Deployed the Streamlit dashboard on GCP
- Helped surface trending products not currently stocked by the store
