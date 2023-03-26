import os
import time
import pytz
import gspread
import streamlit as st
from PIL import Image
from datetime import datetime
from configparser import ConfigParser

from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import UnstructuredURLLoader
from langchain.docstore.document import Document
from langchain.prompts.chat import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains.summarize import load_summarize_chain
from langchain.text_splitter import CharacterTextSplitter

# load config file
config = ConfigParser()
config.read("./config.ini")

IST = pytz.timezone('Asia/Kolkata')

creds = config.get('DEFAULT', 'required_credential_keys').split(", ")

SYSTEM_TEMPLATE = config.get('PROMPTS', 'system_template')
HUMAN_TEMPLATE = config.get('PROMPTS', 'human_template')

# sheet link to see data - https://docs.google.com/spreadsheets/d/1nps81OcyJXbbouIcAux-LV93zo24OW4m7dB6YAXs6Fg/edit?usp=sharing

SHEET_KEY = config.get('GSHEETS', 'sheet_key')
FAILED_ARTICLES_SHEET_NO = int(config.get('GSHEETS', 'failed_articles_sheet_no'))
RUNS_SHEET_NO = int(config.get('GSHEETS', 'runs_sheet_no'))
COMMENTS_SHEET_NO = int(config.get('GSHEETS', 'comments_sheet_no'))

credentials = {}
for cred in creds:
    credentials[cred] = os.environ.get(cred)

# gc = gspread.service_account(filename="credentials.json")
gc = gspread.service_account_from_dict(credentials)
sh = gc.open_by_key(SHEET_KEY)

# Storing basic run info like datetime, input tokens, runtime etc for further analysis.
failed_articles_sheet = sh.get_worksheet(FAILED_ARTICLES_SHEET_NO)
runs_sheet = sh.get_worksheet(RUNS_SHEET_NO)
comment_sheet = sh.get_worksheet(COMMENTS_SHEET_NO)

styles_dict = {
    "Basic Introduction": "Introduce the main topic or article in a concise and engaging manner. Highlight atleast 4 key points and provide a compelling reason for the audience to continue reading",
    "Summary": "Provide a brief summary of the content, focusing on the atleast 4 most important points. Use clear and concise language to make the post easy to read and understand",
    "Key Observations": "Identify the top 5 most important observations or insights from the content and present them in a clear and organized manner. Use bullet points or numbered lists to make the post easy to scan and digest.",
    "Benifits & Limitations": "Highlight the top 4 benefits and limitations of the topic or article, providing a balanced view of both. Use bullet points or numbered lists to make the post easy to read and understand"
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

def validate_email(email):
    """
    This function takes an email as input and returns True if the email is valid, False otherwise.
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

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
st.write("It will take around 1-2 minutes to generate the results. Press the stop generating button if it exceeds 2 mins and rerun the code again")
st.write("Your comments are important for improving the app and resolving any queries you may have, so please feel free to add them at the bottom")
st.markdown("Created by M V Rama Rao. Follow me on LinkedIn 🤗:  [Linkedin](https://www.linkedin.com/in/ramarao-mv/) ")

st.markdown("""---""")

# enter your open ai api key
openai_api_key = st.text_input('**OpenAI API key**', placeholder='Enter your OpenAI API key', type="password")
st.write("Don't have an API key? refer this [video](https://youtu.be/nafDyRsVnXU)")

# enter article url
article_url = st.text_input('**Enter Article UR**L', placeholder='Enter your URL')

# Style options & tone options.
col1, col2 = st.columns(2)
with col1:
   style = st.selectbox(
    '**Select the type of post**',
    ('Basic Introduction', 'Summary', 'Key Observations', 'Benifits & Limitations'))
with col2:
   tone = st.selectbox(
    '**Select the tone**',
    ('Casual', 'Professional', 'Humorous', 'Informative', 'Inspirational'))

# temperature slider
temperature = st.slider('**Select temperature**', 0.0, 2.0, 0.10, step=0.10)

if st.button("Submit"):
    
    if not openai_api_key:
        st.warning('Please insert OpenAI API Key. Instructions [here](https://help.openai.com/en/articles/4936850-where-do-i-find-my-secret-api-key)', icon="⚠️")
        st.stop()

    if "sk-" not in openai_api_key or len(openai_api_key) != 51:
        st.warning("Please insert proper OpenAI API Key. Instructions [here](https://help.openai.com/en/articles/4936850-where-do-i-find-my-secret-api-key)", icon="⚠️")
        st.stop()

    if not article_url:
        st.warning("Please insert Article URL to generate post.")
        st.stop()

    # loading Chat LLM model
    try:
        llm = load_llm(openai_api_key=openai_api_key, temperature=temperature)
    except Exception as e:
        st.warning("Please Enter proper OpenAI API Key. ", icon="⚠️")
        st.stop()

    # loading data from article
    try:
        data = load_text_from_html(url=article_url)
        docs = generate_docs(data=data)
        print("total docs number", len(docs))

        prompt_tokens = llm.get_num_tokens(SYSTEM_TEMPLATE) + llm.get_num_tokens(HUMAN_TEMPLATE)
        for doc in docs:
            doc_tokens = llm.get_num_tokens(doc.page_content)
            print("doc_tokens", doc_tokens)
            combined_tokens = doc_tokens + prompt_tokens
            print("combined_tokens", combined_tokens)
            if combined_tokens >= 3990:
                raise Exception("token limit exceeded. Article cannot be processed temporarily") 

    except Exception as e:
        current_time = datetime.now(IST).strftime("%m/%d/%Y, %H:%M:%S")
        failed_record = [current_time, article_url]
        failed_articles_sheet.append_row(failed_record)
        st.warning("Cannot extract data from this article. Please try different article ", icon="⚠️")
        print(e)
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
    current_time = datetime.now(IST).strftime("%m/%d/%Y, %H:%M:%S")
    success_record = [current_time, input_num_tokens, output_num_tokens, convert(end_time-start_time)[3:]+' mins', style, tone]
    runs_sheet.append_row(success_record)

    st.success(f'Post generation successful. Time taken: {convert(end_time-start_time)[3:]} mins. Please add your experience in the below comments section!! 🤗', icon="✅")

    st.code(post_result, language=None)
    st.cache_resource.clear()




st.markdown("""---""")

st.write("**Add your own comment:**")
form = st.form("comment")
email = form.text_input("Email")
comment_type = form.selectbox('Comment type', 
                ('Feedback', 'Support', 'Testimonial', 'Appreciation', 'Bug report','Feature request', 
                'Review'))

comment = form.text_area("Comment")
comment_submit = form.form_submit_button("Add comment")

if comment_submit:
    if not validate_email(email):
        st.warning("Please enter proper email", icon="⚠️")
        st.warning(e)
        st.stop()

    current_time = datetime.now(IST).strftime("%m/%d/%Y, %H:%M:%S")
    comment_record = [current_time, email, comment, comment_type]
    comment_sheet.append_row(comment_record)
    st.success(f'Comment successfully added.', icon="✅")

