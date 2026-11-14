import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.language_models.fake import FakeListLLM

load_dotenv()

DISCLAIMER = (
    "Lembre-se: esta ferramenta serve para apoiar a decisão e identificar possibilidades, "
    "mas não substitui a sua experiência local. A decisão final é sempre sua."
)


class RotationExplainerAgent:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")

        # Mock para desenvolvimento local sem API Key
        if not api_key:
            self.llm = FakeListLLM(responses=[
                "Esta é uma explicação mockada gerada localmente. A rotação sugerida ajuda na infiltração de água."
            ])
        else:
            self.llm = ChatGoogleGenerativeAI(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                temperature=0.2,
                google_api_key=api_key
            )

        self.prompt = PromptTemplate(
            input_variables=["crop", "benefits", "risks"],
            template="""
            Você é um assistente agronômico. O sistema avaliou a estratégia: {crop}.
            Benefícios esperados: {benefits}.
            Riscos hídricos/climáticos: {risks}.
            
            Explique para um pequeno produtor rural por que esta rotação foi sugerida.
            
            MANDATÓRIO: Conclua a resposta lembrando que esta ferramenta serve para identificar possibilidades,
            mas não substitui a experiência local nem o julgamento do agricultor.
            """
        )
        self.chain = self.prompt | self.llm

    def generate_explanation(self, crop: str, benefits: str, risks: str) -> str:
        response = self.chain.invoke({"crop": crop, "benefits": benefits, "risks": risks})
        text = response.content if hasattr(response, "content") else response
        text = str(text).strip()
        # Regra de segurança mandatória: garante o aviso mesmo se o LLM/mock omitir.
        if "decisão final" not in text.lower():
            text = f"{text}\n\n{DISCLAIMER}"
        return text
