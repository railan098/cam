import cv2
import mysql.connector
import os
import numpy as np
from datetime import datetime

# ==========================================
# CONFIGURAÇÕES GERAIS DO SISTEMA
# ==========================================

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'seguranca'
}

# Região Restrita (Posição X, Posição Y, Largura, Altura)
ZONA_PROIBIDA = [150, 100, 350, 300] 

# Sensibilidade
SENSIBILIDADE = 25       # Menor = mais sensível (Padrão: 50)
AREA_MINIMA = 800        # Menor = detecta objetos menores

PASTA_FOTOS = 'capturas'

# ==========================================

class SistemaSeguranca:
    def __init__(self):
        # Cria a pasta de fotos se não existir
        if not os.path.exists(PASTA_FOTOS):
            os.makedirs(PASTA_FOTOS)

        # Tenta conectar na câmera automaticamente (índices comuns no Linux)
        self.cap = self._conectar_camera()
        
        # IA de Subtração de Fundo
        self.subtrator = cv2.createBackgroundSubtractorMOG2(
            history=500, 
            varThreshold=SENSIBILIDADE, 
            detectShadows=True
        )
        self.alarme_disparado = False

    def _conectar_camera(self):
        """Tenta abrir a câmera em várias portas diferentes para evitar o erro de Index."""
        indices_para_testar = [0, 1, 2, 4]
        for idx in indices_para_testar:
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                print(f"[OK] Câmera conectada com sucesso no dispositivo /dev/video{idx}")
                return cap
        
        print("\n[ERRO CRÍTICO] Nenhuma câmera encontrada!")
        print("-> Verifique se outro programa (Navegador/Zoom) está usando a câmera.")
        print("-> Verifique as permissões rodando: sudo usermod -aG video $USER")
        exit()

    def processar_imagem(self, roi):
        """Limpa a imagem e destaca apenas o movimento real."""
        mask = self.subtrator.apply(roi)
        _, mask = cv2.threshold(mask, 250, 255, cv2.THRESH_BINARY)
        
        # Filtros morfológicos para remover "chuviscos" e sombras
        kernel = np.ones((3,3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.dilate(mask, kernel, iterations=2)
        return mask

    def registrar_ocorrencia(self, frame):
        """Salva a foto física e grava o log no MySQL XAMPP."""
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        caminho_arquivo = os.path.join(PASTA_FOTOS, f"alerta_{ts}.jpg")
        
        # 1. Salva a foto
        if cv2.imwrite(caminho_arquivo, frame):
            try:
                # 2. Salva no Banco de Dados
                conn = mysql.connector.connect(**DB_CONFIG)
                cursor = conn.cursor()
                sql = "INSERT INTO deteccoes (mensagem, caminho_foto) VALUES (%s, %s)"
                val = ("Invasão na Zona Restrita", caminho_arquivo)
                cursor.execute(sql, val)
                conn.commit()
                conn.close()
                print(f"[ALERTA] Invasão! Foto salva: {caminho_arquivo}")
            except Exception as e:
                print(f"[ERRO DB] Falha ao conectar no XAMPP: {e}")

    def iniciar_monitoramento(self):
        print("-" * 40)
        print("MONITORAMENTO DE ALTA SENSIBILIDADE ATIVO")
        print("Pressione 'q' na janela do vídeo para sair")
        print("-" * 40)
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Conexão com a câmera perdida.")
                break

            # Define a Região de Interesse (ROI)
            x, y, w, h = ZONA_PROIBIDA
            roi = frame[y:y+h, x:x+w]
            
            # Aplica os filtros apenas dentro da caixa definida
            mascara = self.processar_imagem(roi)
            contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            movimento_na_zona = False
            
            # Analisa tudo que se moveu
            for c in contornos:
                area = cv2.contourArea(c)
                if area > AREA_MINIMA:
                    movimento_na_zona = True
                    
                    # Desenha um quadrado verde ao redor da pessoa/objeto
                    (ox, oy, ow, oh) = cv2.boundingRect(c)
                    cv2.rectangle(frame, (x+ox, y+oy), (x+ox+ow, y+oy+oh), (0, 255, 0), 2)

            # Desenha a Zona Proibida na tela principal
            # Vermelho se invadido, Azul Claro se seguro
            cor_caixa = (0, 0, 255) if movimento_na_zona else (255, 255, 0)
            cv2.rectangle(frame, (x, y), (x+w, y+h), cor_caixa, 2)
            cv2.putText(frame, "AREA RESTRITA", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor_caixa, 2)

            # Dispara banco de dados apenas uma vez por evento
            if movimento_na_zona and not self.alarme_disparado:
                self.registrar_ocorrencia(frame)
                self.alarme_disparado = True
            elif not movimento_na_zona:
                self.alarme_disparado = False

            # Exibe a imagem
            cv2.imshow("Central de Seguranca", frame)

            # Trava de segurança para fechar (Tecla Q)
            if cv2.waitKey(30) & 0xFF == ord('q'):
                break

        # Limpa tudo ao fechar
        self.cap.release()
        cv2.destroyAllWindows()

# Inicializa o script
if __name__ == "__main__":
    sistema = SistemaSeguranca()
    sistema.iniciar_monitoramento()