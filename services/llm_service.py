from utils.custom_llm import OurLLM

llm = OurLLM()
def call_llm(prompt):

    response = llm.complete(prompt)
    print(response)
    return response.text.strip()   # .text gives the clean string output