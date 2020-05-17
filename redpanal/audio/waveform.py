# Requires pydub (with ffmpeg) and Pillow
#
# Usage: python waveform.py <audio_file>

import sys

from PIL import Image, ImageDraw


class Waveform(object):

    db_ceiling = 60

    def __init__(self, audio_file, width, height, bar_count):
        self.width = width
        self.height = height
        self.bar_count = bar_count

        audio_file = audio_file
        self.peaks = self._calculate_peaks(audio_file)

    def _calculate_peaks(self, audio_file):
        """ Returns a list of audio level peaks """
        chunk_length = len(audio_file) / self.bar_count

        loudness_of_chunks = [audio_file[i * chunk_length: (i + 1) * chunk_length].rms
                              for i in range(self.bar_count)]

        max_rms = max(loudness_of_chunks) * 1.00

        return [int((loudness / max_rms) * self.db_ceiling)
                for loudness in loudness_of_chunks]

    def _get_bar_image(self, size, fill):
        """ Returns an image of a bar. """
        width, height = size
        bar = Image.new('RGBA', size, fill)

        end = Image.new('RGBA', (width, 2), fill)
        draw = ImageDraw.Draw(end)
        draw.point([(0, 0), (3, 0)], fill='#c1c1c150')
        draw.point([(0, 1), (3, 1), (1, 0), (2, 0)], fill='#c1c1c150')

        bar.paste(end, (0, 0))
        bar.paste(end.rotate(180), (0, height - 2))
        return bar

    def _generate_waveform_image(self):
        """ Returns the full waveform image """
        im = Image.new('RGBA', (self.width, self.height), '#ffffffff')
        for index, value in enumerate(self.peaks, start=0):
            column_space = self.width/self.bar_count
            column = int(index * column_space)
            upper_endpoint = int(self.height/2 - value)
            value = value or 1
            im.paste(self._get_bar_image((4, value * 2), '#42424250'),
                     (column, upper_endpoint))

        return im

    def save(self, filename):
        """ Save the waveform as an image """
        with open(filename, 'wb') as imfile:
            self._generate_waveform_image().save(imfile, 'PNG')



if __name__ == '__main__':
    filename = sys.argv[1]
    from pydub import AudioSegment
    sound = AudioSegment.from_file(filename)
    waveform = Waveform(sound, width=940, height=150, bar_count=940/8)
    waveform.save(sys.argv[2])
