# FAQ Polymer

List the frequent problems encountered while programming with Polymer.

## How to redirect to another page?

https://github.com/PolymerElements/app-route/issues/150#issuecomment-251306074

```javascript
window.history.pushState({}, null, '/intro');
window.dispatchEvent(new CustomEvent('location-changed'));
``` 



## How to expose a CSS variable?

```css
:host {
  /* Basic use case */
  color: var(--typio-component-color, #00aabb);
  
  /* Advanced syntax to avoid specifying the default each time the variable is used */
  --effective-height: var(--typio-component-height, 20px);
}
```

Example: see `typio-speech-bubble`
