# \<typio\>

Practice deliberately touch typing.

**Important**: This project is under development. You could access the latest version at: [https://typio-59500.firebaseapp.com/](https://typio-59500.firebaseapp.com/)


## Presentation

*Typio* is a web editor to practice touch typing on various types of content:

* Source code using famous projects hosted by GitHub (Docker, Linux, Git, Hadoop, etc.). All major programming languages are represented: JavaScript, Java, C, C++, Python, PHP, Ruby, Shell, C#, Go, Swift, Scala, Haskell, Lua, Clojure, Rust, Erlang, and many others.

* Classic literature using Public Domain books hosted by Project Gutenberg. For now, only languages based on latin script are supported: English, French, German, Spanish, Italian, Portuguese, and others.

* Other sources are planned: lyrics, quotations, etc.

Here is a preview of the editor:

![Preview](/images/preview.png)


## Motivations


*TypeRacer* is excellent to compete with other typists but do not help you to identify your weaknesses and work specifically on it. To reach expert performance, research reveals we need to practice on the hardest parts (see [deliberate practice][dp]). The aim of *Typio* is to help you focus on these most challenging aspects. After each practice session, the editor reveals statistics (WPM, unproductive keystroke overhead, most difficult keys, etc.). While not currently implemented, *Typio* will let you create your own drills based on the hardest key combinations to practice specifically on your weaknesses. So, *Typio* is the perfect complement to practice alone before competing on *TypeRacer*.


## Install

The application uses the [Polymer 2.0](https://www.polymer-project.org/) framework. While not the most popular web framework, Polymer embraces web standards and requires minimal rewrites between versions (a good point for a side project.)

To install the application on your machine, make sure you have the [Polymer CLI](https://www.npmjs.com/package/polymer-cli) installed. Then run `polymer serve` to serve the application locally.

Then, follow the URL displayed on the output.

## Building

```
$ polymer build
```

This will create builds of your application in the `build/` directory, optimized to be served in production. You can then serve the built versions by giving `polymer serve` a folder to serve from:

```
$ polymer serve build/default
```

## Deploying

The application is deployed on Firebase Hosting. To deploy the application, you need to install the Firebase CLI first. Then, run `firebase deploy`. 

Check the [complete procedure](https://firebase.google.com/docs/hosting/deploying) for more information.

Note: If this is the first time you deploy, you need to configure the Firebase application using the command `firebase init`.


## Running Tests

Polymer uses [web-component-tester](https://github.com/Polymer/web-component-tester). To run the tests, run `polymer test`.

```
$ polymer test
```


[dp]: https://en.wikipedia.org/wiki/Practice_(learning_method)#Deliberate_practice
