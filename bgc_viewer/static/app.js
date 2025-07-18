async function fetchData(endpoint, outputId) {
    const outputElement = document.getElementById(outputId);
    const preElement = outputElement.querySelector('pre');
    
    // Show loading state
    preElement.textContent = 'Loading...';
    preElement.className = 'loading';
    
    try {
        const response = await fetch(endpoint);
        const data = await response.json();
        
        // Format and display the JSON response
        preElement.textContent = JSON.stringify(data, null, 2);
        preElement.className = response.ok ? '' : 'error';
        
    } catch (error) {
        preElement.textContent = `Error: ${error.message}`;
        preElement.className = 'error';
    }
}

// Add some interactive features
document.addEventListener('DOMContentLoaded', function() {
    // Add click-to-copy functionality to code elements
    const codeElements = document.querySelectorAll('code');
    codeElements.forEach(code => {
        code.style.cursor = 'pointer';
        code.title = 'Click to copy';
        
        code.addEventListener('click', function() {
            navigator.clipboard.writeText(this.textContent).then(() => {
                const original = this.textContent;
                this.textContent = 'Copied!';
                setTimeout(() => {
                    this.textContent = original;
                }, 1000);
            });
        });
    });
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case '1':
                    e.preventDefault();
                    fetchData('/api/data', 'data-output');
                    break;
                case '2':
                    e.preventDefault();
                    fetchData('/api/users', 'users-output');
                    break;
                case '3':
                    e.preventDefault();
                    fetchData('/api/stats', 'stats-output');
                    break;
                case '4':
                    e.preventDefault();
                    fetchData('/api/health', 'health-output');
                    break;
            }
        }
    });
    
    // Auto-refresh health check every 30 seconds
    setInterval(() => {
        fetchData('/api/health', 'health-output');
    }, 30000);
    
    // Initial health check
    fetchData('/api/health', 'health-output');
});
