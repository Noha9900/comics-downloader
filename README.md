# Universal Manga & Comic Telegram Bot (2GB Edition)

A massive-scale Telegram bot capable of downloading chapters or full comics from 10,000+ websites (8muses, MangaFire, etc.) using `gallery-dl`. 

It automatically compiles downloaded images into PDF format. To bypass Telegram's standard 50MB bot limit, this stack includes a local Telegram Bot API server, unlocking **2GB file uploads for all users**. If a comic exceeds 1.9GB, it dynamically splits the comic into multiple PDF volumes to prevent server crashes.

## Features
* **Universal Scraping:** Powered by `gallery-dl`.
* **Auto-PDF Conversion:** Fast, lossless conversion using `img2pdf`.
* **2GB Uploads:** Routes traffic through a local API server.
* **Auto-Splitting:** Safely chunks massive 1000-chapter downloads into 1.9GB parts.
* **Custom Renaming:** Asks the user if they want to rename the file before processing.

## Setup Requirements
You will need to get your `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org) to run the Local Bot API server.

## Environment Variables
Create a `.env` file or set these in your hosting provider (Render/VPS):
* `BOT_TOKEN`: Your Telegram Bot Token from BotFather.
* `TELEGRAM_API_ID`: Your API ID.
* `TELEGRAM_API_HASH`: Your API Hash.
