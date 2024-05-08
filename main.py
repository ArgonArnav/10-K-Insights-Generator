from flask import Flask, render_template, request, jsonify
from pydantic import BaseModel
from typing import List
import requests
import matplotlib.pyplot as plt
import google.generativeai as genai
from wordcloud import WordCloud
from sec_edgar_downloader import Downloader
import os
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

genai_api_key = "AIzaSyCGFaJB7dMn0ZidStYJubn2JnUiqWnvwRU"
genai.configure(api_key=genai_api_key)

model = genai.GenerativeModel('gemini-pro')

app = Flask(__name__)

class GetQuestionAndFactsResponse(BaseModel):
    facts: List[str]
    status: str

facts_dict = {
    'documents': [],
    'facts': [],
    'status': ''
}

def download_10k_filings(tickers):
    dl = Downloader(company_name="UTD", email_address="anandarnav2021@gmail.com")

    for ticker in tickers:
        try:
            # Download 10-K filing for the given year and ticker
            dl.get("10-K", ticker, after="1995-01-01", before="2023-12-31")
            print(f"Downloaded {ticker}")
        except Exception as e:
            print(f"Failed to download {ticker}: {e}")

tickers = ["AAPL", "MSFT", "GOOGL"] 

download_10k_filings(tickers)

def process_documents(documents):
    facts = []

    for doc in documents:
        response = model.generate_content(
            f"Question: Give some insights from the following 10-K fillings information in 1 line \nDocument:\n{doc}"
        )

        extracted_facts = response.text.strip().split("\n")

        for fact in extracted_facts:
            if "remove:" in fact:
                fact_to_remove = fact.replace("remove:", "").strip()
                if fact_to_remove in facts:
                    facts.remove(fact_to_remove)
            elif fact not in facts:
                facts.append(fact)

    return facts

def generate_wordcloud(facts):
    if not facts:
        print("No facts to generate word cloud")
        return
    
    text = ' '.join(facts)
    wordcloud = WordCloud(width=800, height=400, background_color ='white', stopwords=None, min_font_size=10).generate(text)
    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.tight_layout(pad=0)
    plt.savefig('static/wordcloud.png')


def read_10k_filings(ticker, max_lines=1000):
    filings_content = []

    directory = f'sec-edgar-filings/{ticker}/'
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = []
                        for i, line in enumerate(f):
                            lines.append(line)
                            if i + 1 >= max_lines:
                                break
                        text = ''.join(lines)
                        words = re.findall(r'\b\w+\b', text)
                        words = ' '.join(words)
                        filings_content.append(words)
                    print(f"Read {file}")
                except Exception as e:
                    print(f"Failed to read {file}: {e}")

    return filings_content



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit_question_and_documents', methods=['POST'])
def submit_question_and_documents():
    req_data = request.get_json()

    if not req_data:
        return jsonify(error="No JSON data received"), 400

    # question = req_data.get('question')
    ticker = req_data.get('ticker')

    if not ticker:
        return jsonify(error="Ticker not provided"), 400

    global facts_dict
    facts_dict = {
        # 'question': question,
        'documents': read_10k_filings(ticker, max_lines=30),
        'status': 'done'
    }

    return jsonify({}), 200


@app.route('/get_question_and_facts', methods=['GET'])
def get_question_and_facts():
    global facts_dict
    print(facts_dict)
    if facts_dict:
        if facts_dict['status'] == 'processing':
            return jsonify({
                'status': 'processing'
            }), 200
        elif facts_dict['status'] == 'done':
            facts = process_documents(facts_dict['documents'])
            facts_dict['facts'] = facts
            facts_dict['status'] = 'done'
            generate_wordcloud(facts)
            response = GetQuestionAndFactsResponse(**facts_dict)
            # Clear facts_dict
            facts_dict = {
                'documents': [],
                'facts': [],
                'status': ''
            }
            return jsonify(response.dict()), 200

    return jsonify(error="No question and documents submitted"), 400

@app.route('/process', methods=['POST'])
def process():
    docs = [request.files[file].read().decode('utf-8') for file in request.files]
    extracted_facts = process_documents(docs)

    return render_template('result.html', extracted_facts=extracted_facts)

@app.route('/visualization')
def visualization():
    return render_template('visualization.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5001,debug=True)