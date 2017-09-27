const functions = require('firebase-functions');
const http = require('http');

// // Create and Deploy Your First Cloud Functions
// // https://firebase.google.com/docs/functions/write-firebase-functions

// Documentation to create a Cloud Function using Firebase
// see https://firebase.google.com/docs/functions/get-started

exports.extractContent = functions.https.onRequest((request, response) => {

  // Documentation of the module http.request in NodeJS
  // https://nodejs.org/api/http.html#http_http_request_options_callback

  const url = request.query.url;
  // Only GitHub URLs are supported right now.
  // Ex: https://github.com/spring-projects/spring-framework/blob/master/spring-core/src/main/java/org/springframework/core/BridgeMethodResolver.java

  // By default, the URL corresponds to the HTML version. To retrieve the raw content, we use this URL instead:
  // https://raw.githubusercontent.com/spring-projects/spring-framework/master/spring-core/src/main/java/org/springframework/core/BridgeMethodResolver.java
  const path = url.replace('https://github.com/', '')

  const options = {
    hostname: 'raw.githubusercontent.com',
    port: 443,
    path: path,
    method: 'GET',
//    headers: {
//      'Referer': url
//    }
  };

  const req = http.request(options, (res) => {
    let str = '';

    res.setEncoding('utf8');
    res.on('data', (chunk) => {
      str += chunk;
    });
    res.on('end', () => {
      response.send(str);
    });
  });

  req.on('error', (e) => {
    console.error(`problem with request: ${e.message}`);
  });

  req.end(); // call the URL
});
