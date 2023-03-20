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
You are a Linkedin post creator. 
I want you to create a linkedin post using the below text.

The below text is not developed by myself. I am creating a linkedin post around that text.
The post should consists of atleast 7 to 8 paragraphs of content.
Your goal is to:
- Properly understand the text.
- Generate post based on specified flavour.
- Convert the post to a third person mode. 
- Convert the post to a specified tone.

Here are some examples different Tones:
- Formal: We went to Barcelona for the weekend. We have a lot of things to tell you.
- Informal: Went to Barcelona for the weekend. Lots to tell you.
"""

human_msge_template = """
Please start the linkedin post with a title. 

Below is the text, flavour, and tone:
TEXT: {text}
FLAVOUR: {flavour}
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
# gc = gspread.service_account(filename=credentials_file)
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

flavours_dict = {
    "Basic Introduction Post": "Create Introduction linkedin post for the article",
    "Summary Post": "Summarize the content and create a post using summary",
    "Key Observations Post": "List out 10 most important observations in bullet points",
    "Benifits & Limitations Post": "List out top benifits and limitations in bullet points"
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
st.write("Compared to other OpenAI models, it is cheaper and more accurate, and it will take around 2 minutes to generate the results.")
st.write("In the future versions, will utilize more open source Language models to generate results")
st.markdown("Created by M V Rama Rao. Follow me on LinkedIn 🤗:  [Linkedin](https://www.linkedin.com/in/ramarao-mv/) ")

# enter your open ai api key
openai_api_key = st.text_input('OpenAI API key', placeholder='Enter your OpenAI API key')

# enter article url
article_url = st.text_input('Enter Article URL', placeholder='Enter your URL')

# flavour options & tone options & temperature
col1, col2 = st.columns(2)
with col1:
   flavour = st.selectbox(
    'Select the type of post',
    ('Basic Introduction Post', 'Summary Post', 'Key Observations Post', 'Benifits & Limitations Post'))
with col2:
   tone = st.selectbox(
    'Select the tone',
    ('Informal', 'formal'))
    # ('Casual', 'Formal', 'Humorous', 'Persuasive', 'Informative', 'Emotional'))

# temp slider
temperature = st.slider('Select temperature', 0.0, 1.0, 0.10, step=0.10)

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

    with st.spinner(text="Generating post..."):
    # for i in range(3):
        start_time = time.time() 
        chain = load_summarize_chain(llm, chain_type="map_reduce", 
                                    return_intermediate_steps=False, map_prompt=chat_prompt, combine_prompt=chat_prompt)
        result = chain({"input_documents": docs, "flavour": flavours_dict[flavour], "tone": tone}, return_only_outputs=True)
        post_result = result['output_text']
        end_time = time.time()
    # my_bar.progress((i + 1)*33, text="Generating posts...")

    st.success(f'Post generation successful. Time taken:{convert(end_time-start_time)[3:]}', icon="✅")

    st.code(post_result, language=None)

    # for num, result in enumerate(post_results):
    #     st.write(f"Variation {num+1}")
    #     st.code(result, language=None)


if st.button("Clear All Data"):
    # Clears all st.cache_resource caches:
    st.cache_resource.clear()





