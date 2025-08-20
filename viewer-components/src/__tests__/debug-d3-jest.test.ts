import * as d3 from 'd3';

// Simple test to debug what's happening with D3 in Jest
test('debug D3 in Jest', () => {
  console.log('=== D3 Debug Test ===');
  console.log('d3:', typeof d3);
  console.log('d3.select:', typeof d3.select);

  try {
    console.log('document.body:', !!document.body);
    
    const selection = d3.select(document.body);
    console.log('d3.select(body):', typeof selection);
    console.log('selection.append:', typeof selection.append);
    
    const div = selection.append('div');
    console.log('after append div:', typeof div);
    console.log('div.attr:', typeof div.attr);
    
    const withAttr = div.attr('class', 'test');
    console.log('after attr:', typeof withAttr);
    console.log('withAttr.style:', typeof withAttr.style);
    
    // Let's inspect the object
    console.log('withAttr keys:', Object.keys(withAttr));
    console.log('withAttr constructor:', withAttr.constructor.name);
    
  } catch (error) {
    console.error('Error:', error);
  }
  
  expect(true).toBe(true); // Just to make it a valid test
});
