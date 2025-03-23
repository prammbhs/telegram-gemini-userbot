// Demo Chat Functionality
document.addEventListener('DOMContentLoaded', function() {
    const demoMessages = document.getElementById('demo-messages');
    const demoForm = document.getElementById('demo-form');
    const demoInput = document.getElementById('demo-message');
    const sampleQuestions = document.querySelectorAll('.sample-question');
    
    // Demo responses database
    const responses = {
        "what is blockchain": "Blockchain is a distributed, decentralized ledger technology that records transactions across many computers. Each block contains a timestamp and link to the previous block, forming a chain. It's the foundation of cryptocurrencies like Bitcoin, but has many other applications including supply chain tracking, voting systems, and smart contracts.",
        
        "explain cloud computing": "Cloud computing delivers computing services—including servers, storage, databases, networking, software, and analytics—over the internet. Instead of owning and maintaining physical servers, you rent resources as needed. This provides benefits like flexibility, cost savings, easy scalability, and automatic updates.",
        
        "how does ai work": "AI works by using algorithms to process large amounts of data, identify patterns, and make predictions or decisions based on that analysis. Modern AI uses techniques like neural networks that simulate human brain function. These systems learn from training data and improve over time. Specialized hardware like GPUs helps process the complex calculations required.",
        
        "what are the latest tech trends": "Current tech trends include AI advancements (particularly generative AI like ChatGPT), quantum computing, edge computing, extended reality (XR), sustainable tech, 5G expansion, and Web3 technologies. Cybersecurity continues to evolve as threats become more sophisticated.",
        
        "best programming language to learn": "The 'best' programming language depends on your goals. For web development, JavaScript is essential. Python is great for beginners, data science, and AI. Java remains popular for enterprise applications. For mobile apps, consider Swift (iOS) or Kotlin (Android). SQL is crucial for database work. Rather than asking which is best, consider what you want to build.",
        
        "difference between ml and ai": "AI (Artificial Intelligence) is the broader concept of machines being able to carry out tasks in a way we consider 'smart'. Machine Learning (ML) is a subset of AI where we give machines access to data and let them learn for themselves. ML focuses specifically on algorithms that can learn from and make predictions based on data, while AI encompasses a wider range of approaches to mimic human intelligence.",
        
        "what is 5g": "5G is the fifth generation of mobile network technology. It offers faster speeds (up to 10 Gbps), lower latency (1ms vs 50ms for 4G), and greater capacity than previous generations. This enables new applications like autonomous vehicles, smart cities, augmented reality, and the expansion of IoT. 5G uses higher frequency radio waves to achieve these benefits.",
        
        "explain iot": "The Internet of Things (IoT) refers to the network of physical objects embedded with sensors, software, and connectivity that enables them to collect and exchange data. This includes everything from smart home devices and wearables to industrial equipment and city infrastructure. IoT allows for remote monitoring, automation, and data-driven decision making across many domains."
    };
    
    // Add a message to the chat
    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'} mb-3`;
        
        // Position message - user messages are right-aligned
        if (isUser) {
            messageDiv.classList.add('text-end');
        }
        
        const messageContent = document.createElement('div');
        messageContent.className = `message-content ${isUser ? 'bg-primary text-white' : ''}`;
        messageContent.style.display = 'inline-block';
        messageContent.style.padding = '0.75rem 1rem';
        messageContent.style.borderRadius = '1rem';
        messageContent.style.maxWidth = '80%';
        messageContent.textContent = content;
        
        const messageTime = document.createElement('div');
        messageTime.className = 'message-time text-muted';
        messageTime.style.fontSize = '0.8rem';
        messageTime.textContent = 'Just now';
        
        messageDiv.appendChild(messageContent);
        messageDiv.appendChild(messageTime);
        demoMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        demoMessages.scrollTop = demoMessages.scrollHeight;
    }
    
    // Get bot response
    function getBotResponse(userMessage) {
        const lowerCaseMessage = userMessage.toLowerCase().trim();
        
        // Check for exact matches first
        if (responses[lowerCaseMessage]) {
            return responses[lowerCaseMessage];
        }
        
        // Check for partial matches
        for (const key in responses) {
            if (lowerCaseMessage.includes(key) || key.includes(lowerCaseMessage)) {
                return responses[key];
            }
        }
        
        // Fallback response
        return "That's an interesting question! As an AI assistant, I can help with various tech topics like blockchain, cloud computing, AI, programming languages, and tech trends. Feel free to ask about any of these!";
    }
    
    // Handle user message submission
    demoForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const userMessage = demoInput.value.trim();
        if (!userMessage) return;
        
        // Add user message
        addMessage(userMessage, true);
        demoInput.value = '';
        
        // Simulate thinking time
        setTimeout(() => {
            // Add bot response
            const botResponse = getBotResponse(userMessage);
            addMessage(botResponse);
        }, 1000);
    });
    
    // Handle sample question clicks
    sampleQuestions.forEach(button => {
        button.addEventListener('click', function() {
            const question = this.textContent;
            demoInput.value = question;
            demoForm.dispatchEvent(new Event('submit'));
        });
    });
});

// Format large numbers with commas
function formatNumber(num) {
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1,');
}

// Animated counter functionality
function animateCounter(element) {
    const target = parseInt(element.getAttribute('data-target'));
    const duration = parseInt(element.getAttribute('data-duration') || '2000');
    const step = Math.ceil(target / (duration / 16)); // 60fps
    let current = 0;
    
    const timer = setInterval(() => {
        current += step;
        if (current >= target) {
            clearInterval(timer);
            element.textContent = formatNumber(target);
        } else {
            element.textContent = formatNumber(current);
        }
    }, 16);
}

// Animate counters when they come into view
document.addEventListener('DOMContentLoaded', function() {
    const counters = document.querySelectorAll('.counter');
    
    // Use Intersection Observer if available
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });
        
        counters.forEach(counter => {
            observer.observe(counter);
        });
    } else {
        // Fallback for browsers without IntersectionObserver
        counters.forEach(counter => {
            animateCounter(counter);
        });
    }
});
