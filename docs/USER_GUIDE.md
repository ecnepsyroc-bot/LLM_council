# LLM Council User Guide

Welcome to LLM Council, a multi-LLM deliberation system that provides thoughtful, balanced answers by combining the perspectives of multiple AI models.

## Table of Contents

1. [What is LLM Council?](#what-is-llm-council)
2. [How It Works](#how-it-works)
3. [Getting Started](#getting-started)
4. [Using the Interface](#using-the-interface)
5. [Understanding Results](#understanding-results)
6. [Configuration](#configuration)
7. [FAQ](#faq)

---

## What is LLM Council?

LLM Council is a deliberation system that harnesses the collective intelligence of multiple large language models (LLMs). Instead of relying on a single AI's perspective, it:

- **Gathers diverse viewpoints** from multiple state-of-the-art models
- **Anonymously evaluates** each response to prevent model bias
- **Synthesizes** a final answer that incorporates the best insights

This approach produces more nuanced, well-reasoned responses than any single model alone.

---

## How It Works

LLM Council uses a three-stage deliberation process:

### Stage 1: Initial Responses

Your question is sent simultaneously to multiple AI models (the "council"). Each model provides its independent response without seeing what others have written.

**Models in the default council:**
- Claude (Anthropic)
- GPT-4 (OpenAI)
- Gemini (Google)
- Grok (xAI)
- DeepSeek
- And others

### Stage 2: Peer Review

Each council member receives all responses, but with the model identities hidden (labeled "Response A", "Response B", etc.). They evaluate and rank the responses based on:

- Accuracy and correctness
- Depth of insight
- Clarity of explanation
- Practical usefulness

This anonymization prevents models from favoring their own responses or those of "prestigious" models.

### Stage 3: Final Synthesis

A designated "chairman" model (typically Claude) reviews all initial responses along with the peer evaluations. It then synthesizes a final answer that:

- Incorporates the strongest elements from each response
- Addresses areas of disagreement
- Provides a balanced, comprehensive conclusion

---

## Getting Started

### Prerequisites

- Modern web browser (Chrome, Firefox, Safari, Edge)
- Network access to the LLM Council server

### Accessing the Interface

1. Open your browser and navigate to the LLM Council URL
2. The main chat interface will load automatically
3. You can start asking questions immediately

### First Question

1. Type your question in the input box at the bottom
2. Press Enter or click the Send button
3. Wait for all three stages to complete
4. Review the synthesized answer in Stage 3

---

## Using the Interface

### Main Components

#### Conversation List (Left Sidebar)
- View all your past conversations
- Pin important conversations
- Rename or delete conversations
- Create new conversations

#### Chat Area (Center)
- View the full conversation history
- Expand/collapse individual stages
- Navigate between responses using tabs

#### Input Area (Bottom)
- Type your questions here
- Press Enter to send
- Press Shift+Enter for a new line

### Conversation Management

**Creating a New Conversation:**
- Click the "+" button in the sidebar
- Or simply start typing in an empty chat

**Renaming a Conversation:**
- Hover over a conversation in the sidebar
- Click the edit icon
- Enter the new name

**Pinning a Conversation:**
- Hover over a conversation
- Click the pin icon
- Pinned conversations appear at the top

**Deleting a Conversation:**
- Hover over a conversation
- Click the delete icon
- Confirm the deletion

---

## Understanding Results

### Stage 1: Individual Responses

Each tab shows a different model's response to your question. Key things to notice:

- **Model Name**: Shown at the top of each tab
- **Response Content**: The full answer from that model
- **Confidence Score**: How confident the model is (when available)

Use this stage to see the range of perspectives on your question.

### Stage 2: Peer Evaluations

This stage shows how each model evaluated the responses:

- **Evaluation Text**: Each model's analysis of all responses
- **Rankings**: How each model ranked the responses (best to worst)
- **Aggregate Rankings**: Combined rankings showing overall consensus

**Note:** Model names shown in bold are for readability only. The models received anonymous labels (Response A, B, C, etc.) to ensure unbiased evaluation.

### Stage 3: Final Synthesis

The green-highlighted section contains the final synthesized answer. This represents:

- The best insights from all council members
- Resolution of any disagreements
- A comprehensive, balanced response

**This is typically the answer you want to use.**

---

## Configuration

### Available Models

The default council includes frontier models from major AI providers. The exact lineup may vary based on server configuration.

### Chairman Selection

The chairman model (responsible for final synthesis) can be configured. By default, this is Claude, known for nuanced synthesis capabilities.

### API Configuration

If you're running your own instance:

1. Copy `.env.example` to `.env`
2. Add your OpenRouter API key
3. Optionally customize the council models

```env
OPENROUTER_API_KEY=your_key_here
COUNCIL_MODELS=anthropic/claude-opus-4,openai/gpt-4.5,google/gemini-2.5-pro
CHAIRMAN_MODEL=anthropic/claude-opus-4
```

---

## FAQ

### Why does the response take time?

LLM Council queries multiple models in parallel and runs a multi-stage deliberation process. While optimized for speed, this naturally takes longer than a single-model response (typically 15-45 seconds).

### Why do the models sometimes disagree?

Different models have different training data, architectures, and perspectives. Disagreement is normal and valuable—it highlights areas of uncertainty or where multiple valid viewpoints exist.

### Can I trust the final synthesis?

The synthesis aims to provide a balanced view, but you should:
- Review the individual responses if the topic is critical
- Check the peer rankings to understand consensus
- Use your own judgment for important decisions

### What if one model gives a much better answer?

The Stage 2 rankings will reflect this, and the Stage 3 synthesis will incorporate the strongest elements. You can also view Stage 1 directly to see individual responses.

### Are my conversations private?

Conversations are stored on the server you're connected to. For privacy:
- Delete sensitive conversations after use
- Consider self-hosting for maximum privacy
- Review the server's data retention policy

### How do I report issues?

- For bugs or feature requests: Open an issue on GitHub
- For server-specific issues: Contact your administrator

---

## Tips for Best Results

1. **Be Specific**: Clear, detailed questions get better responses
2. **Provide Context**: Include relevant background information
3. **Review All Stages**: Don't just read Stage 3—the individual responses offer valuable perspectives
4. **Check Rankings**: The peer evaluation shows model consensus (or disagreement)
5. **Iterate**: Ask follow-up questions to dive deeper

---

*LLM Council - Better answers through collaboration*
