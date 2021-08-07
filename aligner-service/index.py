# -*- coding: utf-8 -*-
import cherrypy
import sys
from subprocess import run
from montreal_forced_aligner.command_line.mfa import main as mfa
from tempfile import TemporaryDirectory
from shutil import rmtree
from os import mkdir

acoustic_model = '/home/kruza/aligner/acoustic_model.zip'

class Aligner(object):
  @cherrypy.expose
  def index(self):
    return '''
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="UTF-8" />
          <title>text-audio aligner</title>
        </head>
        <body>
          <form action="align" enctype="multipart/form-data" method="post">
            <textarea name="transcript" placeholder="přepis"></textarea>
            <br />
            <input type="file" name="audio" />
            <br />
            <input type="submit" />
          </form>
        </body>
      </html>
    '''
  @cherrypy.expose
  def align(self, transcript, audio):
    if cherrypy.request.method == 'OPTIONS':
      cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'

    request_id = str(cherrypy.request.unique_id)
    tempdir = TemporaryDirectory()
    datadir = '%s/%s' % (tempdir.name, request_id)
    outdir = '%s/out' % (tempdir.name)
    mkdir(datadir)
    mkdir(outdir)
    unformatted_audio_fn = '%s/alignee-%s' % (datadir, audio.filename)
    audio_fn = '%s/alignee.wav' % (datadir)
    if isinstance(audio, str):
      unformatted_audio_fn = audio
    else:
      with open(unformatted_audio_fn, 'wb') as f:
        while True:
          data = audio.file.read(8192)
          if not data:
            break
          f.write(data)
    run(['sox', unformatted_audio_fn, audio_fn, 'remix', '-', 'rate', '16k'])
    dictfn = '%s/dictionary' % (datadir)
    dict_result = run(['bash', '/home/kruza/aligner/mkdict.sh'], capture_output = True, input = transcript, text = True)
    with open(dictfn, 'w') as f:
      f.write(dict_result.stdout)
    with open('%s/alignee.lab' % (datadir), 'w') as f:
      f.write(transcript)
    sys.argv = [
      'mfa',
      'align',
      '-c',
      datadir,
      dictfn,
      acoustic_model,
      outdir,
    ]
    # return ' '.join(sys.argv)
    mfa()
    rmtree('/home/kruza/Documents/MFA/%s' % (request_id))
    cherrypy.response.headers['Content-Type'] = 'text/plain'
    with open('%s/%s_alignee.TextGrid' % (outdir, request_id), 'r') as f:
      return f.read()

cherrypy.config.update({
  'server.socket_host': '0.0.0.0',
  'server.socket_port': 8080,
})

cherrypy.quickstart(Aligner())
