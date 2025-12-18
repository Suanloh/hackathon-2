# AI Emergency Response Navigator (AERN)
### TEAM: INSOMIA

---
## ⭐ Overview

This repository presents an end-to-end prototype for **LLM-powered credit risk assessment**, integrating structured applicant data with unstructured information extracted from PDFs, images, and CSV files. The system combines OCR, regex-based data extraction, LLM-driven behavioural risk analysis, rule-based decision overrides, and transparent explainability via an interactive Streamlit dashboard.
The application demonstrates how **Large Language Models (LLMs)** can enhance traditional credit scoring by identifying behavioural risk signals that are not captured by conventional numerical features, enabling more informed and interpretable credit decisions.

---

# 1. Industry Context
   
   Emergency response systems worldwide struggle with:
- Slow, unclear, or inaccessible safety instructions
- Panic behaviour during floods, fires, earthquakes, accidents
- Lack of personalized step-by-step guidance for different environments
- Limited hotline capacity (999/911 often overloaded)
- Fragmented information from multiple agencies

With LLMs, authorities and rescue organizations can now analyze:
- Real-time user inputs (text/voice)
- Location-based risk levels
- Emergency severity
- Behavioural cues (“my house is shaking”, “water rising”, “I smell gas”)


Emergencies require instant, accurate, and context-aware instructions—something static PDFs, posters, or hotlines cannot provide.

# 2. Problem Statement
How can we build an AI-powered system that provides reliable, life-saving, and context-specific emergency guidance to the public during disasters and accidents?

# 3. Challenge
Build a prototype using LLMs that:
- Assesses the user’s emergency situation
- Asks key clarifying questions
- Provides correct safety instructions based on context
- Suggests nearest help (shelters, hospitals, fire stations)
- Generates an emergency action plan
- Works in multiple emergency types (flood, fire, injury, chemical hazard)

# 4. AI Opportunity
LLMs can:
- Interpret unstructured emergency descriptions (“my house is flooding up to my knees”)
- Detect severity level from emotional + contextual cues
- Be combined with geolocation and real-time hazard data
- Provide simple, step-by-step instructions tailored to the user
- Generate clear and human-friendly guides even under panic
- Summarize and communicate incidents to rescuers or authorities
Optional expansion:
- Multimodal: analyse images of fire, flood water level, injuries
- Predict risk progression (“water rising → leave house within 20 minutes”)

# 5. Optional Resources
- Open disaster datasets (flood zones, past incident logs)
- Real-time hazard APIs (weather, air quality, flood alerts)
- OpenStreetMap for shelters, hospitals, police/fire stations
- LLM APIs (OpenAI, Gemini, Llama, JamAI)
- Geolocation APIs for routing
- Synthetic emergency text (messages, panic descriptions, voice transcripts)



# 6. Judging Criteria
### ✔ Reliability
Does the system give correct, safe emergency instructions?
### ✔ LLM Reasoning
Does it understand messy human input like:
“water already masuk rumah sampai lutut, what do I do?”
### ✔ Personalization
Does the AI adapt guidance based on:
- location
- severity
- user constraints (children, elderly, disabilities)?
### ✔ Interpretability
Does it show:
- why it assessed the situation as high/medium/low risk?
- why it gave specific steps?
### ✔ UI / Dashboard
- Is the interface clear under panic?
- Is the emergency plan easy to follow?
### ✔ End-to-End Functionality
Can the prototype:
- take an emergency description
- classify the situation
- generate instructions
- point to nearby help
- summarize for rescue teams?

