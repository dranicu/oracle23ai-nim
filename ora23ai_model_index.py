import os
import oracledb
from ora23ai_connection import db_connection
from langchain_community.vectorstores.oraclevs import OracleVS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.documents import Document
from langchain_community.document_loaders import CSVLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def inject_metadata(doc):
    content = doc.page_content

    try:
        source_file = os.path.basename(doc.metadata['source'])
    except:
        source_file = doc.metadata['source']

    return f"Name of the file for this content: `{source_file}` Content: `{content}`"
    
def create_vector_store_index(collection_name, file_path, embedding):
    
    if not file_path:
        return "Please try again"
        
    file_path_split = file_path.split(".")
    file_type = file_path_split[-1].rstrip('/')

    if file_type == 'csv':
        loader = CSVLoader(file_path=file_path)
        documents = loader.load()
    
    elif file_type == 'pdf':
        loader = PyPDFLoader(file_path)
        pages = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 1024,
        chunk_overlap = 128,)

        documents = text_splitter.split_documents(pages)
    else:
        loader = TextLoader(file_path=file_path)
        pages = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 1024,
        chunk_overlap = 128,)

        documents = text_splitter.split_documents(pages)

    enriched_documents = [Document(inject_metadata(doc), metadata=doc.metadata) for doc in documents]
    adb_pwd, dns, dbwallet_dir, dbwallet_dir, atp_wallet_pwd = db_connection()
    adb_user = "vectoruser"
    
    db_client = oracledb.connect(
        user=adb_user,
        password=adb_pwd,
        dsn=dns, 
        config_dir=dbwallet_dir,
        wallet_location=dbwallet_dir,
        wallet_password=atp_wallet_pwd)
    
    sql = "SELECT table_name FROM all_tables WHERE owner='VECTORUSER' AND TABLE_NAME!='DBTOOLS$EXECUTION_HISTORY'"
    c = db_client.cursor()
    c.execute(sql)
    result = c.fetchall()
    tables = []
    for table in result:
        tables.append(table[0].lower())
    
    if collection_name in tables:        
        vectordb = OracleVS(
            client=db_client, 
            embedding_function=embedding,
            table_name=collection_name,
        )
        vectordb.add_documents(
            documents = enriched_documents
        )
    else:
        OracleVS.from_documents(
            enriched_documents,
            embedding,
            client=db_client,
            table_name=collection_name,
            distance_strategy=DistanceStrategy.COSINE,
        )
    

    db_client.close()
    return "Vector store index is created."