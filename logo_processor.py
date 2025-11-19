from PIL import Image

def processar_logo_e_mudar_cor(caminho_entrada, caminho_saida, cor_fundo_para_remover=(0, 0, 0), tolerancia_fundo=20, limite_texto_escuro=150):
    """
    Remove o fundo de uma imagem, tornando-o transparente, e muda os pixels
    escuros da legenda para a cor branca.

    Args:
        caminho_entrada (str): Caminho para a imagem de entrada ("FisioManager.png").
        caminho_saida (str): Caminho para salvar a imagem de saída.
        cor_fundo_para_remover (tuple): A cor RGB do fundo a ser removido (padrão é preto).
        tolerancia_fundo (int): A margem de tolerância para a cor do fundo (0-255).
        limite_texto_escuro (int): O limite máximo de brilho RGB para considerar um pixel como "texto escuro"
                                   e mudá-lo para branco.
    """
    try:
        # 1. Abre a imagem e converte para RGBA (para ter canal Alpha/transparência)
        img = Image.open(caminho_entrada).convert("RGBA")
        datas = img.getdata()

        novos_dados = []
        for item in datas:
            r, g, b, a = item
            
            # --- Lógica 1: Remover o Fundo (Preto) ---
            # Verifica se o pixel é a cor de fundo (preto, com tolerância)
            if (abs(r - cor_fundo_para_remover[0]) < tolerancia_fundo and
                abs(g - cor_fundo_para_remover[1]) < tolerancia_fundo and
                abs(b - cor_fundo_para_remover[2]) < tolerancia_fundo):
                
                # Torna o pixel totalmente transparente (Alpha = 0)
                novos_dados.append((0, 0, 0, 0)) 
                
            # --- Lógica 2: Mudar a Legenda Escura para Branco ---
            # A legenda (cinza escuro/prata) é escura, mas não tanto quanto o fundo, 
            # e tem cores R, G, B parecidas.
            # Usamos o limite de brilho e verificamos se não foi o fundo.
            elif r < limite_texto_escuro and g < limite_texto_escuro and b < limite_texto_escuro:
                 # Torna o pixel branco sólido (R=255, G=255, B=255, Alpha=255)
                 novos_dados.append((255, 255, 255, 255))
                 
            # --- Lógica 3: Manter o Ícone Original ---
            else:
                # Mantém o pixel (aplica-se ao ícone azul e qualquer outra cor)
                novos_dados.append(item)

        img.putdata(novos_dados)
        img.save(caminho_saida, "PNG")
        print(f"Processamento concluído: Fundo transparente e legenda em branco. Imagem salva em: {caminho_saida}")

    except FileNotFoundError:
        print(f"Erro: O arquivo '{caminho_entrada}' não foi encontrado. Certifique-se de que 'FisioManager.png' está na mesma pasta.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

# --- Como usar a função ---
if __name__ == "__main__":
    # A chamada abaixo remove o fundo preto (0,0,0) e transforma 
    # todos os pixels escuros (como a legenda cinza) em branco.
    processar_logo_e_mudar_cor(
        "FisioManager.png", 
        "FisioManager_FundoTransparente_LegendaBranca.png", 
        cor_fundo_para_remover=(0, 0, 0), 
        tolerancia_fundo=10,
        limite_texto_escuro=150
    )

    print("\nVocê precisará instalar a biblioteca Pillow: `pip install Pillow`")