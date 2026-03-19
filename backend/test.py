import google.generativeai as genai

genai.configure(api_key="AIzaSyBTSq4lNMrHzOm5fiCIARkf4MzJltQ_OAw")

for m in genai.list_models():
    if "generateContent" in m.supported_generation_methods:
        print(m.name)