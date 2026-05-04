# Reze AI Chatbot

## Overview
This repository contains a Python-based AI chatbot application. The bot is heavily equipped with a vast local database of Reze reaction images and memes. It is designed to process conversational inputs through an external AI handler, manage user interactions via a database, and dynamically serve specific image assets based on the chat context. 

The project is pre-configured for continuous hosting and cloud deployment.

## Architecture and Core Files

The repository is structured to separate the AI logic, database management, and deployment protocols into distinct modules:

*   `main.py`: The entry point and core loop of the chatbot. This script handles the initialization, connects to the messaging platform's API, and routes incoming messages to the appropriate handlers.
*   `ai_handler.py`: The brain of the operation. This module intercepts user prompts and processes them through an external LLM API to generate in-character conversational responses.
*   `db.py`: The database management module. It handles reading and writing user data, maintaining context history, and ensuring the bot retains memory across sessions and restarts.
*   `keep_alive.py`: A lightweight web server script (typically utilizing Flask) designed to bind to a port. This is a pragmatic solution used to keep the bot awake on free-tier hosting platforms by allowing an external service to ping it continuously.
*   `Procfile`: Contains the deployment directive (`web: python main.py`). This indicates the bot is ready to be deployed on container-based Platform-as-a-Service (PaaS) providers.
*   `requirements.txt`: The dependency ledger, listing all required Python libraries.
*   `assets/memes/`: A local storage directory stockpiled with Reze reaction images. The assets cover a wide spectrum of triggers (e.g., annoyed, sleepy, excited, psycho) as well as several NSFW categories. The bot pulls from this directory to send image attachments during specific conversational triggers.

## Setup and Installation

To run this project locally or prepare it for deployment, follow these steps:

1.  **Environment Preparation**
    Ensure Python 3.x is installed on your system. It is highly recommended to use a virtual environment to avoid dependency conflicts.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use: venv\Scripts\activate
    ```

2.  **Install Dependencies**
    Install the necessary packages from the requirements ledger.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment Variables**
    Create a `.env` file in the root directory. You will need to provide the necessary API keys for your setup to function. This typically includes:
    *   The Bot Token for your target platform.
    *   The API Key for your AI provider.

4.  **Database Initialization**
    If `db.py` requires initial schema setup, execute that module first or ensure `main.py` handles the table creation on its initial run.

5.  **Execution**
    Launch the bot.
    ```bash
    python main.py
    ```

## Per-Server Configuration

If deploying this bot across multiple servers (guilds), server administrators must configure the following settings upon inviting the bot to ensure proper functionality and prevent spam:

*   **Channel Whitelisting:** By default, the bot should be restricted from reading all channels. Use the designated admin commands to set specific `allowed_channels` where the bot is permitted to read and respond to messages.
*   **Context Isolation:** The database (`db.py`) is structured to separate conversation memory by `server_id` and `channel_id`. If memory appears to bleed between servers, ensure database partitions are correctly mapped.
*   **Meme Cooldowns:** The bot utilizes assets from the `assets/memes/` folder. To prevent chat flooding, configure the image trigger probability or set strict time-based cooldowns per server.
*   **Admin Roles:** Ensure the correct server roles are assigned so that only authorized users can wipe the bot's memory context or change its operational channels.

## Deployment Strategies

You have two primary deployment methods built into this repository:

**Method 1: Containerized Cloud Hosting**
The inclusion of the `Procfile` allows for seamless deployment to PaaS providers. Simply push the repository to your host, configure your environment variables in their respective dashboards, and the host will automatically execute `python main.py` as the web worker.

**Method 2: Always-On Services**
If you are hosting this on a platform that puts inactive processes to sleep, the `keep_alive.py` file is your failsafe. Ensure `main.py` imports and runs the `keep_alive` function. Then, set up an external service to ping the provided web address every 5 minutes.

## Disclaimer
Review the contents of your `assets/memes/` directory before deploying this bot to public servers. Ensure you are not violating the Terms of Service of your messaging platform or your AI provider by serving the NSFW assets included in this repository.
