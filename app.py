import os
import json
import time
from datetime import datetime
from PIL import Image
import gspread
import streamlit as st

from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import UnstructuredURLLoader
from langchain.docstore.document import Document
from langchain.prompts.chat import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains.summarize import load_summarize_chain
from langchain.text_splitter import CharacterTextSplitter
from configparser import ConfigParser

# load config file
config = ConfigParser()
config.read("./config.ini")

creds = config.get('DEFAULT', 'required_credential_keys').split(", ")

SYSTEM_TEMPLATE = config.get('PROMPTS', 'system_template')
HUMAN_TEMPLATE = config.get('PROMPTS', 'human_template')

# sheet link to see data - https://docs.google.com/spreadsheets/d/1nps81OcyJXbbouIcAux-LV93zo24OW4m7dB6YAXs6Fg/edit?usp=sharing

SHEET_KEY = config.get('GSHEETS', 'sheet_key')
FAILED_ARTICLES_SHEET_NO = int(config.get('GSHEETS', 'failed_articles_sheet_no'))
RUNS_SHEET_NO = int(config.get('GSHEETS', 'runs_sheet'))

credentials = {}
for cred in creds:
    credentials[cred] = os.environ.get(cred)

# gc = gspread.service_account(filename="credentials.json")
gc = gspread.service_account_from_dict(credentials)
sh = gc.open_by_key(SHEET_KEY)

# Storing basic run info like datetime, input tokens, runtime etc for further analysis.
failed_articles_sheet = sh.get_worksheet(FAILED_ARTICLES_SHEET_NO)
runs_sheet = sh.get_worksheet(RUNS_SHEET_NO)

styles_dict = {
    "Basic Introduction Post": "Introduce the topic or article in a concise and engaging manner. Highlight the key points and provide a compelling reason for the audience to continue reading",
    "Summary Post": "Provide a brief summary of the content, focusing on the most important points. Use clear and concise language to make the post easy to read and understand",
    "Key Observations Post": "Identify the most important observations or insights from the content and present them in a clear and organized manner. Use bullet points or numbered lists to make the post easy to scan and digest.",
    "Benifits & Limitations Post": "Highlight the top benefits and limitations of the topic or article, providing a balanced view of both. Use bullet points or numbered lists to make the post easy to read and understand"
}

@st.cache_resource
def load_text_from_html(url):
    loader = UnstructuredURLLoader(urls=[url])
    data = loader.load()
    return data

def generate_docs(data):
    text_splitter = CharacterTextSplitter()
    texts = text_splitter.split_text(data[0].page_content)
    docs = [Document(page_content=t) for t in texts]
    return docs

def load_llm(openai_api_key, temperature):
    llm = ChatOpenAI(openai_api_key=openai_api_key, temperature=temperature)
    return llm

def create_chatprompt(system_template, human_msge_template):
    system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)
    human_message_prompt = HumanMessagePromptTemplate.from_template(human_msge_template)
    chat_prompt = ChatPromptTemplate.from_messages([system_message_prompt, human_message_prompt])
    return chat_prompt

def convert(seconds):
    return time.strftime("%H:%M:%S", time.gmtime(seconds))

def get_doc_num_tokens(text, llm):
    return llm.get_num_tokens(text)

# Page introductions
icon_image = Image.open("icon.png")

st.set_page_config(
    page_title="Linkedin Content Creator",
    page_icon=icon_image,
    layout="wide")

image = Image.open('linkedin.png')
st.image(image)

st.title('Linkedin Posts Creator Using ChatGPT')
st.write("A demo app to create LinkedIn posts based on an article/blog using ChatGPT API")
st.write("The app will generate the post based on the type, once you provide your OpenAI API key and the article link. ")
st.write("It will take around 2 minutes to generate the results. Press the stop generating button if it exceeds 2 mins and rerun the code again")
st.write("I am planning to add more open source LLMs in future versions and also incorporate the functionality of inputting YouTube videos and generating posts based on the video's content.")
st.write("Stay tuned for the later updates!!")
st.markdown("Created by M V Rama Rao. Follow me on LinkedIn 🤗:  [Linkedin](https://www.linkedin.com/in/ramarao-mv/) ")

# enter your open ai api key
openai_api_key = st.text_input('OpenAI API key', placeholder='Enter your OpenAI API key')

# enter article url
article_url = st.text_input('Enter Article URL', placeholder='Enter your URL')

# Style options & tone options.
col1, col2 = st.columns(2)
with col1:
   style = st.selectbox(
    'Select the type of post',
    ('Basic Introduction Post', 'Summary Post', 'Key Observations Post', 'Benifits & Limitations Post'))
with col2:
   tone = st.selectbox(
    'Select the tone',
    ('Casual', 'Professional', 'Humorous', 'Informative', 'Inspirational'))

# temperature slider
temperature = st.slider('Select temperature', 0.0, 2.0, 0.10, step=0.10)

if st.button('Submit'):
    
    if not openai_api_key:
        st.warning('Please insert OpenAI API Key. Instructions [here](https://help.openai.com/en/articles/4936850-where-do-i-find-my-secret-api-key)', icon="⚠️")
        st.stop()

    if "sk-" not in openai_api_key or len(openai_api_key) != 51:
        st.warning("Please insert proper OpenAI API Key. Instructions [here](https://help.openai.com/en/articles/4936850-where-do-i-find-my-secret-api-key)", icon="⚠️")
        st.stop()

    if not article_url:
        st.warning("Please insert Article URL to generate post.")
        st.stop()

    # loading data from article
    try:
        data = load_text_from_html(url=article_url)
        docs = generate_docs(data=data)
        print("total docs number", len(docs))

    except Exception as e:
        current_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        failed_record = [current_time, article_url]
        failed_articles_sheet.append_row(failed_record)
        st.warning("Cannot extract data from this article. Please try different article ", icon="⚠️")
        st.stop()
        
    
    # loading Chat LLM model
    try:
        llm = load_llm(openai_api_key=openai_api_key, temperature=temperature)
    except Exception as e:
        st.warning("Please Enter proper OpenAI API Key. ", icon="⚠️")
        st.stop()

    chat_prompt = create_chatprompt(system_template=SYSTEM_TEMPLATE, human_msge_template=HUMAN_TEMPLATE)

    # input data token lengths
    input_num_tokens = get_doc_num_tokens(data[0].page_content, llm)

    start_time = time.time() 

    if st.button("Stop Generating"):
        st.warning("post not generated", icon="⚠️")
        st.stop()
    
    try:
        with st.spinner(text="Generating post..."):

            chain = load_summarize_chain(llm, chain_type="map_reduce", map_prompt=chat_prompt, combine_prompt=chat_prompt)
            result = chain({"input_documents": docs, "style": styles_dict[style], "tone": tone})
            post_result = result['output_text']
            end_time = time.time()
    except Exception as e:
        st.warning("Error occured", icon="⚠️")
        st.warning(e)
        st.stop()


    output_num_tokens = get_doc_num_tokens(post_result, llm)
    current_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    success_record = [current_time, input_num_tokens, output_num_tokens, convert(end_time-start_time)[3:]+' mins', style, tone]
    runs_sheet.append_row(success_record)

    st.success(f'Post generation successful. Time taken: {convert(end_time-start_time)[3:]} mins', icon="✅")

    st.code(post_result, language=None)
    st.cache_resource.clear()