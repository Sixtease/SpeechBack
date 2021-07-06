# -*- coding: utf-8 -*-
import cherrypy
import sys
import json
from cherrypy.lib.static import serve_file
from subprocess import run
from montreal_forced_aligner.command_line.mfa import main as mfa
from tempfile import TemporaryDirectory
from shutil import rmtree
from os import mkdir

acoustic_model = '/home/kruza/aligner/acoustic_model.zip'

def get_audio_splits(audio_path, audio_id):
  audio_length = run(['soxi', '-D', audio_path], capture_output = True, text = True)
  splitpoints = []

  step = 120
  prev_timepos = 0
  timepos = prev_timepos + step
  while True:
    if timepos > audio_length:
      splitpoints.append({
        'duration': step,
        'basename': '%s--from-%.2f--to-%.2f.mp3' % (audio_id, prev_timepos, audio_length),
        'from': prev_timepos,
        'to': audio_length,
      })
      break
    splitpoints.append({
      'duration': step,
      'basename': '%s--from-%.2f--to-%.2f.mp3' % (audio_id, prev_timepos, timepos),
      'from': prev_timepos,
      'to': timepos,
    })
    prev_timepos = timepos
    timepos = timepos + step

  meta = { audio_id: { 'formats': { 'mp3': splitpoints } } }
  return 'jsonp_splits(\n%s\n)\n' % (json.dumps(meta))

class Aligner(object):
  def _align(self, workdir):  # workdir must include alignee.{wav,lab}
    dictfn = '%s/dictionary' % (workdir)
    transfn = '%s/alignee.lab' % (workdir)
    outdir_obj = TemporaryDirectory()
    outdir = outdir_obj.name
    transcript = None;
    with open(transfn, 'r') as f:
      transcript = f.read()
    dict_result = run(['bash', '/home/kruza/aligner/mkdict.sh'], capture_output = True, input = transcript, text = True)
    with open(dictfn, 'w') as f:
      f.write(dict_result.stdout)
    sys.argv = [
      'mfa',
      'align',
      '-c',
      workdir,
      dictfn,
      acoustic_model,
      outdir,
    ]
    mfa()
    aligned = None
    with open('%s/%s_alignee.TextGrid' % (outdir, request_id), 'r') as f:
      aligned = f.read()

    alignment_id = os.path.basename(workdir)
    rmtree('/home/kruza/Documents/MFA/%s' % (alignment_id))

    return aligned


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
    unformatted_audio_fn = '%s/alignee.audio' % (datadir)
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
    with open('%s/alignee.lab' % (datadir), 'w') as f:
      f.write(transcript)
    aligned = self._align(datadir)
    cherrypy.response.headers['Content-Type'] = 'text/plain'
    with open('%s/%s_alignee.TextGrid' % (outdir, request_id), 'r') as f:
      return f.read()

  @cherrypy.expose
  def submit_audio(self, audio, transcript):
    if cherrypy.request.method == 'OPTIONS':
      cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'

    request_id = str(cherrypy.request.unique_id)
    workdir = '/tmp/%s' % (request_id)
    mkdir(workdir)
    unformatted_audio_fn = '%s/%s' % (workdir, 'orig_audio')
    audio_fn = '%s/%s' % (workdir, 'alignee.wav')

    with open(unformatted_audio_fn, 'wb') as f:
      while True:
        data = audio.file.read(8192)
        if not data:
          break
        f.write(data)

    run(['sox', unformatted_audio_fn, audio_fn, 'remix', '-', 'rate', '16k'])

    transcript_fn = '%s/%s' % (workdir, 'alignee.lab')
    with open(transcript_fn, 'w') as f:
      f.write(transcript)

    aligned = self._align(workdir)

    audio_split_metadata = get_audio_splits(audio_fn, request_id)

    cherrypy.response.headers['Content-Type'] = 'text/json'
    return json.dumps({
      'status': 'OK',
      'session': request_id,
      'aligned':  aligned,
      'split_meta': audio_split_metadata,
    })

  @cherrypy.expose
  def audio_chunk(self, session, start, end):
    workdir = '/tmp/%s' % (session)
    source_audio_fn = '%s/%s' % (workdir, 'orig_audio')
    chunk_fn = '%s/%s--from-%.2f--to-%.2f.mp3' % (workdir, session, start, end)
    run(['sox', source_audio_fn, chunk_fn, 'trim', start, '=%s' % (end)])
    return serve_file(chunk_fn, content_type='audio/mpeg')


cherrypy.config.update({
  'server.socket_host': '0.0.0.0',
  'server.socket_port': 8080,
})

cherrypy.quickstart(Aligner())
