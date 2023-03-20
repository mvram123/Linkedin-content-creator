import os
import json
import time
import gspread
import streamlit as st
from datetime import datetime
from PIL import Image
from langchain.chat_models import ChatOpenAI
from langchain.prompts.chat import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.document_loaders import UnstructuredURLLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.docstore.document import Document
from langchain.chains.summarize import load_summarize_chain

system_template = """
You are a LinkedIn post creator. 
I would like you to create a post using the text provided below. 
Please note that I did not develop this text. 
I need your expertise to turn it into a LinkedIn post.

Your goal is to:
1. Understand the text properly.
2. Generate a post that reflects the specified style or approach.
3. Convert the post to third-person mode.
4. Use the specified tone.
5. Write a post that is at least 400 words long.

Here are some examples different Tones:
- Casual: "Don't Miss Out on These Awesome Event Trends!"
- Professional: "Valuable Insights for Industry Professionals: Key Trends from Recent Event"
- Humorous: "Snacks vs. Insights: The Ultimate Event Showdown!"
- Informative: "Comprehensive Analysis of Key Findings from Recent Event"
- Inspirational: "Pushing Boundaries and Exploring New Opportunities: Insights from Recent Event"
"""

human_msge_template = """
Start with a post title.

Below is the text, style, and tone:
TEXT: {text}
STYLE: {style}
TONE: {tone}

YOUR RESPONSE:
"""
# access the sheet with this link - https://docs.google.com/spreadsheets/d/1nps81OcyJXbbouIcAux-LV93zo24OW4m7dB6YAXs6Fg/edit?usp=sharing
creds = ["type", "project_id", "private_key_id", "private_key", "client_email",
        "client_id", "auth_uri", "token_uri", "auth_provider_x509_cert_url", "client_x509_cert_url"]

credentials = {}
for cred in creds:
    credentials[cred] = os.environ.get(cred)

# creds_json = os.environ.get('CREDENTIALS')
# gc = gspread.service_account(filename="credentials.json")
gc = gspread.service_account_from_dict(credentials)
sh = gc.open_by_key("1nps81OcyJXbbouIcAux-LV93zo24OW4m7dB6YAXs6Fg")

# for storing failed articles for further analysis.
failed_articles_sheet = sh.get_worksheet(0)
# comments_sheet = sh.get_worksheet(1)

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

styles_dict = {
    "Basic Introduction Post": "Introduce the topic or article in a concise and engaging manner. Highlight the key points and provide a compelling reason for the audience to continue reading",
    "Summary Post": "Provide a brief summary of the content, focusing on the most important points. Use clear and concise language to make the post easy to read and understand",
    "Key Observations Post": "Identify the most important observations or insights from the content and present them in a clear and organized manner. Use bullet points or numbered lists to make the post easy to scan and digest.",
    "Benifits & Limitations Post": "Highlight the top benefits and limitations of the topic or article, providing a balanced view of both. Use bullet points or numbered lists to make the post easy to read and understand"
}
# Page introductions

#icon image
icon_image = Image.open("icon.png")

st.set_page_config(
    page_title="Linkedin Content Creator",
    page_icon=icon_image,
    layout="wide")

# add image
image = Image.open('linkedin.png')
st.image(image)

st.title('Linkedin Posts Creator Using ChatGPT')
st.write("A demo app to create LinkedIn posts based on an article/blog using ChatGPT API")
st.write("Just enter your OpenAI API key and the article link, and we'll give you the post depending on the type of post. ")
st.write("Compared to other OpenAI models, it is cheaper and more accurate, and it will take around 2 minutes to generate the results. Press the stop button if it exceeds 2 mins and rerun the code again")
st.write("In the future versions, will utilize more open source Language models to generate results")
st.markdown("Created by M V Rama Rao. Follow me on LinkedIn 🤗:  [Linkedin](https://www.linkedin.com/in/ramarao-mv/) ")

# enter your open ai api key
openai_api_key = st.text_input('OpenAI API key', placeholder='Enter your OpenAI API key')

# enter article url
article_url = st.text_input('Enter Article URL', placeholder='Enter your URL')

# flavour options & tone options & temperature
col1, col2 = st.columns(2)
with col1:
   style = st.selectbox(
    'Select the type of post',
    ('Basic Introduction Post', 'Summary Post', 'Key Observations Post', 'Benifits & Limitations Post'))
with col2:
   tone = st.selectbox(
    'Select the tone',
    ('Casual', 'Professional', 'Humorous', 'Informative', 'Inspirational'))
    # ('Casual', 'Formal', 'Humorous', 'Persuasive', 'Informative', 'Emotional'))

# temp slider
temperature = st.slider('Select temperature', 0.0, 2.0, 0.10, step=0.10)

if st.button('Submit'):
    
    if not openai_api_key:
        st.warning('Please insert OpenAI API Key. Instructions [here](https://help.openai.com/en/articles/4936850-where-do-i-find-my-secret-api-key)', icon="⚠️")
        st.stop()

    if not article_url:
        st.warning("Please insert Article URL to generate post.")
        st.stop()

    # loading data from article
    try:
        data = load_text_from_html(url=article_url)

        # generating docs from data
        docs = generate_docs(data=data)
        print("total docs number", len(docs))
    except Exception as e:
        # storing extraction failed articles for further analysis in sheet - https://docs.google.com/spreadsheets/d/1nps81OcyJXbbouIcAux-LV93zo24OW4m7dB6YAXs6Fg/edit?usp=sharing
        # other than failed articles and comments, no other info will be stored.
        
        current_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        failed_record = [current_time, article_url]
        failed_articles_sheet.append_row(failed_record)

        # raise warning
        st.warning("Cannot extract data from this article. Please try different article ", icon="⚠️")
        st.stop()
        
    
    # loading Chat LLM model
    try:
        llm = load_llm(openai_api_key=openai_api_key, temperature=temperature)
    except Exception as e:
        st.warning("Please Enter proper OpenAI API Key. ", icon="⚠️")
        st.stop()

    # generate 3 variations
    # post_results = []
    chat_prompt = create_chatprompt(system_template=system_template, human_msge_template=human_msge_template)
    # my_bar = st.progress(0, text="Generating posts...")

    if st.button("Stop Generating"):
            st.warning("post not generated", icon="⚠️")
            st.stop()

    with st.spinner(text="Generating post..."):
    # for i in range(3):
        start_time = time.time() 
        chain = load_summarize_chain(llm, chain_type="map_reduce", map_prompt=chat_prompt, combine_prompt=chat_prompt)
        result = chain({"input_documents": docs, "style": styles_dict[style], "tone": tone})
        post_result = result['output_text']
        end_time = time.time()
        
    # my_bar.progress((i + 1)*33, text="Generating posts...")

    st.success(f'Post generation successful. Time taken: {convert(end_time-start_time)[3:]} mins', icon="✅")

    st.code(post_result, language=None)
    time.sleep(10)

    st.cache_resource.clear()

    # for num, result in enumerate(post_results):
    #     st.write(f"Variation {num+1}")
    #     st.code(result, language=None)






