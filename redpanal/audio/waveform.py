# redpanal/audio/waveform.py

# Requires pydub (with ffmpeg). PIL is no longer required for JSON output.
#
# Usage: python waveform.py <audio_file> <output_json_file>

import sys
import json
from pydub import AudioSegment


class Waveform(object):
    """
    Clase encargada de analizar el archivo de audio para calcular los
    picos de amplitud (loudness) necesarios para la visualización de la onda.
    """

    db_ceiling = 60 # El valor máximo que puede alcanzar un pico normalizado.

    def __init__(self, audio_file, width, height, bar_count):
        self.width = width
        self.height = height
        self.bar_count = bar_count

        # Se asume que audio_file es un objeto AudioSegment de pydub
        self.audio_file = audio_file 
        self.peaks = self._calculate_peaks()

    def _calculate_peaks(self):
        """ 
        Calcula una lista de picos de nivel de audio (RMS)
        normalizados para el número de barras deseado.
        """
        # Calcular la duración de cada "trozo" de audio
        chunk_length = len(self.audio_file) / self.bar_count

        # 1. Obtener el RMS (Root Mean Square - volumen percibido) de cada trozo
        loudness_of_chunks = [self.audio_file[i * chunk_length: (i + 1) * chunk_length].rms
                              for i in range(self.bar_count)]

        # 2. Encontrar el valor RMS máximo para normalizar
        # Se usa * 1.00 para asegurar que sea float
        max_rms = max(loudness_of_chunks) * 1.00

        # 3. Normalizar los valores y escalarlos al db_ceiling (60)
        # Esto genera la lista de alturas de picos para el frontend
        return [int((loudness / max_rms) * self.db_ceiling)
                for loudness in loudness_of_chunks]

    def save_peaks_to_json(self, filename):
        """ Guarda la lista de picos (self.peaks) en un archivo JSON. """
        
        # El contenido es una lista simple de enteros, ideal para Wavesurfer.js
        with open(filename, 'w') as jsonfile:
            json.dump(self.peaks, jsonfile)


if __name__ == '__main__':
    
    # 1. Validación y Definición de rutas
    if len(sys.argv) < 3:
        print("Uso: python waveform.py <archivo_audio> <archivo_salida_json>")
        sys.exit(1)
        
    audio_filename = sys.argv[1]
    output_json_filename = sys.argv[2]
    
    # 2. Cargar el audio usando pydub
    try:
        sound = AudioSegment.from_file(audio_filename)
    except Exception as e:
        print(f"Error al cargar el archivo de audio con pydub/ffmpeg: {e}")
        sys.exit(1)
        
    # 3. Configuración de la Waveform
    # Mantenemos los valores originales de RedPanal.
    width = 940
    height = 150
    # bar_count determina la resolución del waveform (número de barras/datos)
    bar_count = int(width / 8) 
    
    # 4. Generar la onda y guardar el JSON
    waveform_data = Waveform(sound, width=width, height=height, bar_count=bar_count)
    
    try:
        waveform_data.save_peaks_to_json(output_json_filename)
        print(f"Datos de picos guardados exitosamente en: {output_json_filename}")
    except Exception as e:
        print(f"Error al guardar el archivo JSON: {e}")
        sys.exit(1)