import * as d3 from 'd3';
import { JSDOM } from 'jsdom';

// Set up JSDOM
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>');
global.document = dom.window.document;
global.window = dom.window;

console.log('Testing D3 with JSDOM...');

try {
  // Test basic D3 selection
  const selection = d3.select(document.body);
  console.log('1. d3.select(body) works:', !!selection);
  
  // Test append
  const div = selection.append('div');
  console.log('2. append div works:', !!div);
  
  // Test attr
  const withAttr = div.attr('class', 'test');
  console.log('3. attr works:', !!withAttr);
  
  // Test style - this is where it might fail
  const withStyle = withAttr.style('position', 'absolute');
  console.log('4. style works:', !!withStyle);
  
} catch (error) {
  console.error('Error:', error.message);
  console.error('Stack:', error.stack);
}
