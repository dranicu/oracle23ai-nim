import uuid

from ora23ai_connection import db_connection
import gradio as gr
from ora23ai_model_utils import *


def clean_up_vector_db():
    adb_pwd, dns, dbwallet_dir, dbwallet_dir, atp_wallet_pwd = db_connection()
    adb_user = "ADMIN" 
    db_client = oracledb.connect(
        user=adb_user,
        password=adb_pwd,
        dsn=dns, 
        config_dir=dbwallet_dir,
        wallet_location=dbwallet_dir,
        wallet_password=atp_wallet_pwd)
    
    adb_user_vector = "vectoruser"
   
    sql_get_users = """SELECT * FROM all_users"""
    sql_drop_user = f"""DROP USER {adb_user_vector} CASCADE"""
    sql_create_user = f"""CREATE USER {adb_user_vector} IDENTIFIED BY {adb_pwd} DEFAULT TABLESPACE ORDS_PUBLIC_USER TEMPORARY TABLESPACE temp QUOTA UNLIMITED ON ORDS_PUBLIC_USER"""
    sql_grant_user = f"""GRANT CONNECT, RESOURCE TO {adb_user_vector}"""

    cursor = db_client.cursor()
    cursor.execute(sql_get_users)
    result = cursor.fetchall()
    cursor.close()
    
    if "VECTORUSER" in (user[0] for user in result):
        cursor = db_client.cursor()
        cursor.execute(sql_drop_user)
        cursor.execute(sql_create_user)
        cursor.execute(sql_grant_user)
    else:
        cursor = db_client.cursor()
        cursor.execute(sql_create_user)
        cursor.execute(sql_grant_user)
        
    db_client.close()

def fetch_session_hash(request: gr.Request):
    return request.session_hash

def setup_chatbot(llm_models, embedding_models):
    with gr.Blocks(gr.themes.Soft(primary_hue=gr.themes.colors.slate, secondary_hue=gr.themes.colors.purple)) as demo:
        with gr.Row():
            with gr.Column(scale=0.5, variant='panel'):
                gr.Markdown("## RAG Conversation agent")
                instruction = gr.Textbox(label="System instruction", lines=3, value="You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, just say that you don't know. Keep the answer concise. {context}")
                
                session = gr.Textbox(value=uuid.uuid1, label="Session")
                gr.ChatInterface(
                    fn=bot,
                    additional_inputs=[
                        session,
                    ],
                )
                demo.load(fetch_session_hash, None, session)
    
            with gr.Column(scale=0.5, variant = 'panel'):
                gr.Markdown("## Select the Generation and Embedding Models")
                with gr.Row(equal_height=True):
    
                    with gr.Column():
                        available_llm_models = sorted([ entry for entry in llm_models ])
                        llm = gr.Dropdown(choices=available_llm_models,
                                          value=available_llm_models[0] if len(available_llm_models) else "",
                                          label="Select the LLM")
                        llm_api_key = gr.Textbox(label='Enter your valid LLM API KEY', type = "password")
                    
                        available_embedding_models = sorted([ entry for entry in embedding_models ])
                        
                        embedding_model = gr.Dropdown(choices=available_embedding_models,
                                        value=available_embedding_models[0] if len(available_embedding_models) else "",
                                        label= "Select the embedding model")
                        embedding_api_key = gr.Textbox(label='Enter your embeddings API KEY', type = "password")
    
                    with gr.Column():
                        model_load_btn = gr.Button('Load model', variant='primary',scale=2)
                        load_success_msg = gr.Textbox(show_label=False,lines=1, placeholder="Model loading ...")
                
                gr.Markdown("## Upload Document")
                file = gr.File(type="filepath")
                with gr.Row(equal_height=True):
                    
    
                    with gr.Column(variant='compact'):
                        vector_index_btn = gr.Button('Create vector store', variant='primary', scale=1)
                        vector_index_msg_out = gr.Textbox(show_label=False, lines=1, scale=1, placeholder="Creating vectore store ...")
    
                vector_index_btn.click(lambda arg1, arg2, arg3, arg4: upload_and_create_vector_store(arg1, arg2, arg3, arg4, embedding_models), [file, embedding_model, embedding_api_key, session], vector_index_msg_out)
                
                reset_inst_btn = gr.Button('Reset',variant='primary', size = 'sm')
    
                with gr.Accordion(label="Text generation tuning parameters"):
                    temperature = gr.Slider(label="temperature", minimum=0.1, maximum=1, value=0.7, step=0.05)
                    max_tokens = gr.Slider(label="max_tokens", minimum=500, maximum=8000, value=1000, step=1)
                    frequency_penalty = gr.Slider(label="frequency_penalty", minimum=0, maximum=2, value=0, step=0.1)
                    top_p=gr.Slider(label="top_p", minimum=0, maximum=1, value=0.9, step=0.05)
    
                model_load_btn.click(lambda arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10: load_model(arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10, embedding_models, llm_models), [session, embedding_model, embedding_api_key, llm, llm_api_key, instruction, temperature, max_tokens, frequency_penalty, top_p], load_success_msg, api_name="load_model").success()
                reset_inst_btn.click(reset_sys_instruction, instruction, instruction)
            return demo
            

if __name__ == '__main__':

    clean_up_vector_db()
    
    demo = setup_chatbot(llm_models, embedding_models)
    demo.queue(concurrency_count=3)
    demo.launch(debug=True, share=True)