import os, shutil

from ora23ai_model_index import *
from ora23ai_connection import db_connection
from langchain_community.vectorstores.oraclevs import OracleVS
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.chat_message_histories import ChatMessageHistory


# Global environment variables used to store state based on session_id
store = {}
conversation_rag_chain = {}

def load_model(session_id, embedding_model, embedding_api_key, llm_model, llm_api_key, instruction, temperature, max_tokens, frequency_penalty, top_p, embedding_models, llm_models):

    global conversation_rag_chain

    # Setting up embedding
    
    embedding_function = embedding_models.get(embedding_model, {}).get("embedding_function", None)
    if not embedding_function:
        return "Selected embedding model is not defined."

    embedding = embedding_function(api_key=embedding_api_key)
    
    # Setting up LLM

    llm_function = llm_models.get(llm_model, {}).get("llm_function", None)
    
    if not llm_function:
        return "Selected llm model has not function defined."

    llm = llm_function(
        api_key=llm_api_key, 
        kwargs = {
            'temperature': temperature,
            'max_tokens': max_tokens,
            'frequency_penalty': frequency_penalty,
            'top_p': top_p
        }
    )
    collection_name = ''.join([i for i in embedding_model if not i.isdigit()]).replace("-","")
    # Setting up connection to oracle 23ai
    adb_pwd, dns, dbwallet_dir, dbwallet_dir, atp_wallet_pwd = db_connection()
    adb_user = "vectoruser"
    db_client = oracledb.connect(
        user=adb_user,
        password=adb_pwd,
        dsn=dns, 
        config_dir=dbwallet_dir,
        wallet_location=dbwallet_dir,
        wallet_password=atp_wallet_pwd)
    
    vectordb = OracleVS(
            client=db_client, 
            embedding_function=embedding,
            table_name=collection_name,
        )
    
    retriever = vectordb.as_retriever(search_kwargs={"k": 3})

    ### Contextualize question ###
    contextualize_q_system_prompt = """Given a chat history and the latest user question \
    which might reference context in the chat history, formulate a standalone question \
    which can be understood without the chat history. If the question is not related to the chat history, \
    leave the question intact. Do NOT answer the question, \
    just reformulate it if needed and otherwise return it as is."""
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", instruction),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
        
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "User question: {input}"),
        ]
    )

    
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    ### Answer question ###

    document_prompt = PromptTemplate(
		            input_variables=["page_content", "source"], 
		            template="Context:\n{page_content}\nSource:{source}"
		        )
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt, document_prompt=document_prompt)#, output_parser=CustomOutputParser())
    
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    
    
    conversation_rag_chain[session_id] = RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer"
    )

    
    if conversation_rag_chain.get(session_id, None) is None:
        return f"Failed to load the model {llm_model}"

    return f"'{llm_model}' and '{embedding_model}' models loaded"


def upload_and_create_vector_store(file, embedding_model, embedding_api_key, session, embedding_models):
    
    # Save the uploaded file to a permanent location
    if not file:
        return "File not ready or no file selected."
        
    split_file_name = file.split("/")
    file_name = split_file_name[-1]

    data_folder = os.path.join(os.getcwd(), "data")
    os.makedirs(data_folder, exist_ok=True)
    permanent_file_path = os.path.join(data_folder, file_name)
    shutil.copy(file.name, permanent_file_path)

    # Access the path of the saved file
    print(f"File saved to: {permanent_file_path}")

    
    embedding_function = embedding_models.get(embedding_model, {}).get("embedding_function", None)
    
    if not embedding_function:
        return "Selected model not supported."

    embedding = embedding_function(api_key=embedding_api_key)
    
    collection_name = ''.join([i for i in embedding_model if not i.isdigit()]).replace("-","")
    index_success_msg = create_vector_store_index(collection_name, permanent_file_path, embedding)
    
    return index_success_msg

def get_session_history(session_id):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

def reset_sys_instruction(instruction):

    default_inst = "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, just say that you don't know. Keep the answer concise. {context}"
    return default_inst


def bot(question, history, session_id):
    global conversation_rag_chain

    
    result = conversation_rag_chain[session_id].invoke({"input": question},
        config={
            "configurable": {"session_id": session_id}
        },
    )

    
    return result["answer"]