import json
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage




vault_secrets = "/vault/secrets/appsecrets.json"
vault_json = json.load(open(vault_secrets))
openai_api_key = vault_json["openAiKey"]


os.environ["OPENAI_API_KEY"] = openai_api_key
# llm = ChatOpenAI(model="gpt-4o-mini",temperature=.3, max_tokens = 200); #max_tokens=100 ?
llm = ChatOpenAI(model="gpt-4o", max_tokens = 200); #max_tokens=100 ?
projectSummaryLLM = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens = 500); #max_tokens=100 ?

def askChatGPT(words:str):
    messages = [
        SystemMessage("You are Helpy, a helpful AI assistant"),
        HumanMessage(words)
    ]
    result = llm.invoke(messages)
    return result.content

def evaluateProjectStructure(projectStructureString:str):
    messages = [
        SystemMessage("""You are Helpy, a helpful AI coding assistant.
                      Do your best to avoid making up information, but don't avoid using your intuition to resolve queries.
                      YOUR RESPONSES SHOULD BE CONCISE, ACCURATE, AND TO THE POINT - don't exclude anything important because of this though
                      
                      You will be given a representation of a software project's folder structure.
                      Examine the folder structure and filenames, consider what this information tells you about the project
                      
                      Try to guess what the project is for and how it might work - consider how you might build such a project
                      use confident language
                      Avoid unconfident (it is likely..., it is possible... i suspect... __ might ...  etc.) language!
                      
                      When you are done,
                      RESPOND ONLY WITH: a summary of the project based on available information and knowledge of software engineering/architecture.
                      The summary should contain: The name of the project, what languages/packages/frameworks the project uses, what the project *does*, how it works, and how it might or might not fit into a larger software ecosystem"""),
        HumanMessage(projectStructureString)
    ]
    result = llm.invoke(messages)
    return result.content

def summarizeFile(fileName: str, filecontent: str, fileStructureSummary: str):
    messages = [
        SystemMessage("""You are part of a team of AI assistants working together to help developers understand and work with code.
                      Do your best to avoid making up information, but don't avoid using your intuition to resolve queries.
                      YOUR RESPONSES SHOULD BE CONCISE, ACCURATE, AND TO THE POINT - don't exclude anything important because of this though

                      You are helping to examine the architecture and implementation of code within the project in order to understand it better.
                      
                      You will be given the name and contents of a file along with some general information about the project.
                      Examine the contents of the file and generate a short summary of the file. This summary should include a general overview of the contents of the file, as well as how it relates to other files and the project as a whole"""),
        
        HumanMessage('File-structure and initial findings:\n\n'+fileStructureSummary),
        HumanMessage('Provide a short detailed summary of the following file. Consider including information relevant for developers working on the project as well as wanting to interact with the project externally. \nFileName: ' + fileName + '\n\n'+filecontent)
    ]
    result = llm.invoke(messages)
    return result.content

def summarizeDirectory(directoryName: str, directoryContentSummary: str, fileStructureSummary):
    messages = [
        SystemMessage("""You are part of a team of AI assistants working together to help developers understand and work with code.
                      Do your best to avoid making up information, but don't avoid using your intuition to resolve queries.
                      YOUR RESPONSES SHOULD BE CONCISE, ACCURATE, AND TO THE POINT - don't exclude anything important because of this though

                      You are helping to examine the architecture and implementation of code within the project in order to understand it better.
                      to this end, you will receive a representation of the file structure, as well as an initial assessment of the project.
                      
                      FOR THIS TASK:
                      You will be given the name of a directory, as well as a summary of the contents of the directory.
                      
                      Examine the summaries of the contents and generate a short summary of the directory. This summary should include a general overview of the contents of the directory, as well as how it relates to the  function of the project as a whole."""),
        
        HumanMessage('project directory structure and initial findings:\n\n'+fileStructureSummary),
        HumanMessage('Provide a short detailed summary of the following directory: ' + directoryName + '\n\n' + directoryContentSummary)
    ]
    result = llm.invoke(messages)
    return result.content

def summarizeProject(fileStructureString: str, fileStructureSummary: str,  folderSummaries):
    messages = [
        SystemMessage("""You are part of a team of AI assistants working together to help developers understand and work with code.
                      Do your best to avoid making up information, but don't avoid using your intuition to resolve queries.
                      YOUR RESPONSES SHOULD BE CONCISE, ACCURATE, AND TO THE POINT - don't exclude anything important because of this though

                      You are helping to examine the architecture and implementation of code within the project in order to understand it better.
                      to this end, you will receive a representation of the file structure, as well as additional information about the project.
                      
                      FOR THIS TASK:
                      You will be given the file structure of a project, as well as an initial assessment of the project, and a collection of summaries of the contents of directories within the project.
                      
                      Examine the summarized data and file structure and then generate a short summary of the project.
                      This summary should include:
                      - The name of the project
                      - What languages/packages/frameworks the project uses
                      - What the project does (or what different parts do)
                      - How it works
                      - Any external systems that are implied to exist or interact with the project"""),
        
        HumanMessage('project directory structure :\n\n'+fileStructureString),
        HumanMessage('project directory structure initial assessment:\n\n'+fileStructureSummary),
        HumanMessage('Directory summaries:\n\n'+ folderSummaries),
        HumanMessage('using the data provided, generate your short summary (1.5ish paragraphs), keeping in mind everything you want to include while keeping it short.')
    ]
    result = projectSummaryLLM.invoke(messages)
    return result.content