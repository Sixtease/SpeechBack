# -*- coding: utf-8 -*-
import cherrypy
import sys
from subprocess import run
from tempfile import TemporaryDirectory
from shutil import rmtree
from os import mkdir
import json

class SpeechBack(object):
  @cherrypy.expose
  def submit_audio(self, audio, transcript):
    if cherrypy.request.method == 'OPTIONS':
      cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'

    request_id = str(cherrypy.request.unique_id)
    workdir = '/tmp/%s' % (request_id)
    mkdir(workdir)
    unformatted_audio_fn = '%s/%s' % (workdir, 'orig_audio')
    audio_fn = '%s/%s' % (workdir, 'audio.wav')

    with open(unformatted_audio_fn, 'wb') as f:
      while True:
        data = audio.file.read(8192)
        if not data:
          break
        f.write(data)

    run(['sox', unformatted_audio_fn, audio_fn, 'remix', '-', 'rate', '16k'])

    transcript_fn = '%s/%s' % (workdir, 'transcript.lab')
    with open(transcript_fn, 'w') as f:
      while True:
        data = transcript.file.read(8192)
        if not data:
          break
        f.write(data)
    
    cherrypy.response.headers['Content-Type'] = 'text/json'
    return json.dumps({ 'status': 'OK', 'session': request_id })

cherrypy.config.update({
  'server.socket_host': '0.0.0.0',
  'server.socket_port': 8081,
})

cherrypy.quickstart(SpeechBack())
