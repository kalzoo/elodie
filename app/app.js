var menubar = require('menubar'),
    tray = require('tray'),
    ipc = require('ipc'),
    exec = require('child_process').exec;;

/*
 * The main process listens for events from the web renderer.
 */

// When photos are dragged onto the toolbar and photos are requested to be updated it will fire an 'update-photos' ipc event.
// The web renderer will send the list of photos, type of update and new value to apply
// Once this main process completes the update it will send a 'update-photos-completed' event back to the renderer with information
//  so a proper response can be displayed.
ipc.on('update-photos', function(event, args) {
  console.log('update-photos')
  console.log(args)
  if(typeof(args['files']) === 'undefined' || args['files'].length === 0) {
    console.log('no files passed in to update-photos');
    return;
  }

  update_command = '/Users/jaisenmathai/dev/tools/elodie/update.py'
  if(typeof(args['location']) !== 'undefined') {
    update_command += ' --location="' + args['location'] + '" "' + args['files'].join('" "') + '"';
    console.log(update_command)
    exec(update_command, function(error, stdout, stderr) {
      console.log('out ' + stdout)
      console.log('err ' + stderr)
    });
    event.sender.send('update-photos-success', args);
  } else if(typeof(args['album']) !== 'undefined') {
    update_command += ' --album="' + args['album'] + '" "' + args['files'].join('" "') + '"';
    console.log(update_command)
    exec(update_command, function(error, stdout, stderr) {
      console.log('out ' + stdout)
      console.log('err ' + stderr)
    });
    event.sender.send('update-photos-success', args);
  }
  
})

var mb = menubar(
      {
        preloadWindow: true,
        dir: 'html',
        index: 'location.html',
        pages: {
          'location': 'location.html'
        },
        width: 400,
        height: 350
      }
    )

mb.on('ready', function ready () {
  console.log('app is ready')
  this.tray.setToolTip('Drag and drop files here')
  //this.tray.setImage('img/logo.png')
  this.tray.on('clicked', function clicked () {
    console.log('tray-clicked')
  })
  this.tray.on('drop-files', function dropFiles (ev, files) {
    mb.showWindow()
    console.log('window file name ' + mb.window.getRepresentedFilename())
    mb.window.loadUrl('file://' + mb.getOption('dir') + '/' + mb.getOption('pages')['location'])
    //mb.window.openDevTools();
    mb.window.webContents.on('did-finish-load', function() {
      mb.window.webContents.send('files', files);
      mb.window.webContents.send('preview', files);
    });
  })
})

mb.on('create-window', function createWindow () {
  console.log('create-window')
})

mb.on('after-create-window', function afterCreateWindow () {
})

mb.on('show', function show () {
  this.window.loadUrl('file://' + this.getOption('dir') + '/' + this.getOption('index'))
})

mb.on('after-show', function afterShow () {
  console.log('after-show')
})

mb.on('hide', function hide () {
  console.log('hide')
})

mb.on('after-hide', function afterHide () {
  console.log('after-hide')
})

