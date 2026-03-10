# redpanal/audio/signals.py

import os
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Audio # Asumimos que tu modelo se llama Audio
from .waveform import Waveform # La clase que reescribimos en el Paso 1
from pydub import AudioSegment

# Se recomienda importar la configuración y logging para un código robusto
from django.conf import settings 
import logging
logger = logging.getLogger(__name__)


# Esta función se conecta al evento "después de guardar" del modelo Audio
@receiver(post_save, sender=Audio)
def generate_audio_peaks_json(sender, instance, created, **kwargs):
    """ Genera el archivo JSON de picos de amplitud después de que se crea un audio. """

    # Solo generamos el JSON cuando el objeto es CREADO por primera vez.
    if created: 
        
        # --- Configuración del Waveform (debe coincidir con la de waveform.py) ---
        width = 940
        bar_count = int(width / 8) 
        
        try:
            # 1. Obtener la ruta del archivo de audio en el disco.
            audio_file_path = instance.audio.path
            
            # 2. Definir la ruta de salida del JSON
            # ASUNCIÓN: Guardamos el JSON con el mismo nombre y ruta, pero extensión .json
            # Ejemplo: 'media/audio/cancion.mp3' -> 'media/audio/cancion.json'
            json_output_path = audio_file_path.rsplit('.', 1)[0] + '.json' 

            # 3. Cargar el audio con pydub
            sound = AudioSegment.from_file(audio_file_path)
            
            # 4. Generar la onda y guardar el JSON
            waveform_generator = Waveform(sound, width=width, height=150, bar_count=bar_count)
            waveform_generator.save_peaks_to_json(json_output_path)
            
            logger.info(f"JSON de picos generado para Audio ID: {instance.id} en {json_output_path}")

        except Exception as e:
            logger.error(f"ERROR al generar JSON de picos para audio ID {instance.id}: {e}")
            # Si hay un error (ej. FFmpeg no está instalado), aquí se registra.

# IMPORTANTE: 
# Debes asegurarte de que este archivo signals.py esté siendo importado por tu app.
# La forma estándar de hacerlo es en el método ready() de tu archivo apps.py.