import requests
from bs4 import BeautifulSoup
import json
import openai
import base64
import time
import logging
import os

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}
openai.api_key = os.getenv('OPENAI_API_KEY')

def get_goodreads_info(book_title, book_author):
    search_query = f"{book_title} {book_author if book_author is not None else ''}".replace(' ', '+')
    search_url = f"https://www.goodreads.com/search?q={search_query}"
    response = requests.get(search_url, headers=headers)
    if response.status_code != 200:
        return {
            'rating_value': None,
            'rating_count': None,
            'author': None,
            'best_book_url': None
        }
    
    soup = BeautifulSoup(response.text, 'html.parser')
    book_link_tags = soup.find_all('a', class_='bookTitle')
    logging.info(f"Found {len(book_link_tags)} book links")

    best_book_url = None
    highest_rating_count = -1
    best_book_info = None
    
    for book_link_tag in book_link_tags:
        book_url = f"https://www.goodreads.com{book_link_tag['href']}"
        logging.info(f"Checking book URL: {book_url}")
        book_response = requests.get(book_url, headers=headers)
        if book_response.status_code != 200:
            continue

        book_soup = BeautifulSoup(book_response.text, 'html.parser')
        script_tag = book_soup.find('script', type='application/ld+json')
        
        if script_tag:
            json_data = json.loads(script_tag.string)
            if 'aggregateRating' in json_data and 'author' in json_data:
                rating_count = json_data['aggregateRating'].get('ratingCount', 0)
                logging.info(f"Rating count: {rating_count}")
                if rating_count > highest_rating_count:
                    highest_rating_count = rating_count
                    best_book_url = book_url
                    best_book_info = json_data
                else:
                    logging.info(f"Skipping book with rating count: {rating_count}")

    if best_book_info:
        rating_value = best_book_info['aggregateRating'].get('ratingValue')
        rating_count = best_book_info['aggregateRating'].get('ratingCount')
        author = ', '.join([author['name'] for author in best_book_info['author']]) if isinstance(best_book_info['author'], list) else best_book_info['author']['name']
        return {
            'rating_value': rating_value,
            'rating_count': rating_count,
            'author': author,
            'best_book_url': best_book_url
        }
    return {
            'rating_value': None,
            'rating_count': None,
            'author': None,
            'best_book_url': None
    }

def process_image_with_gpt(image_path):
    with open(image_path, "rb") as image_file:
        # image_data = image_file.read()
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai.api_key}"
        }
        
    payload = {
        'model': "gpt-4o",
        'response_format': { "type": "json_object" },
        'messages': [
            {
                "role": "system",
                "content": "You are a helpful assistant that extracts book titles and authors from images of bookshelves."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text",
                     'text': "List all the books from left to right in the image. Do not miss any single book. Format the output as a JSON with a single key \"books\" whose value is a list. Each element of this list is a JSON with keys \"title\" and \"author\". If the title of a book is unknown or empty, do not include the book in the list. If the title is known but the author is unknown or empty, keep the book but leave the author field empty."
                     },
                    {'type': "image_url",
                     "image_url": {
                         "url": f"data:image/jpeg;base64,{base64_image}",
                        # "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
                         "detail": "high"
                         }
                     }
                    ]
                }
        ]
    }

    retry_count = 0
    max_retries = 1
    backoff_factor = 2
    initial_wait = 1

    while retry_count < max_retries:

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        
        response_data = response.json()
        if response.status_code == 200 and 'usage' in response_data:
            prompt_tokens = response_data['usage']['prompt_tokens']
            completion_tokens = response_data['usage']['completion_tokens']
            input_cost_per_token = 0.0000025
            output_cost_per_token = 0.000010

            estimated_cost = (prompt_tokens * input_cost_per_token) + (completion_tokens * output_cost_per_token)
            print(f"Estimated cost: {estimated_cost}")

        print(json.dumps(response_data, indent=4))

        if response.status_code == 200:
            response = response.json()
            if response and 'choices' in response and len(response['choices']) > 0:
                books_data = response['choices'][0]['message']['content']
                books_list = json.loads(books_data)['books']
                return books_list
            else:
                return []
            
        elif response.status_code == 429:
                retry_count += 1
                wait_time = initial_wait * (backoff_factor ** (retry_count - 1))
                time.sleep(wait_time)
        else:
            break
        
    return []
