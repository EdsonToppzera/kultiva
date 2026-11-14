from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate


class RotationExplainerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(temperature=0.2, model="gpt-4o-mini")
        self.prompt = PromptTemplate(
            input_variables=["crop", "benefits", "risks"],
            template="""
            Você é um assistente agronômico. O sistema sugeriu a cultura {crop}.
            Benefícios esperados: {benefits}.
            Riscos climáticos/geosociais: {risks}.
            Explique para um pequeno produtor rural por que esta rotação foi sugerida,
            destacando o que os dados indicam, mas reforçando que a decisão final é dele.
            """
        )
        self.chain = self.prompt | self.llm

    def generate_explanation(self, crop, benefits, risks):
        return self.chain.invoke({"crop": crop, "benefits": benefits, "risks": risks})
