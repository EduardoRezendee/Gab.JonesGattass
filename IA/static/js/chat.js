document.addEventListener("DOMContentLoaded", function () {
    const dropArea = document.getElementById("drop-area");
    const fileInput = document.getElementById("file-input");
    const fileList = document.getElementById("file-list");
    const uploadForm = document.getElementById("upload-form");
    const chatInput = document.getElementById("chat-input");
    const chatBox = document.getElementById("chat-box");
    const sendButton = document.getElementById("send-message");
    
    let uploadedFiles = [];

    // ✅ Função para adicionar arquivos ao chat
    function handleFiles(files) {
        for (let file of files) {
            uploadedFiles.push(file);
            const listItem = document.createElement("li");
            listItem.innerHTML = `${file.name} 
                <span class="remove-file" onclick="removeFile('${file.name}')">❌</span>`;
            fileList.appendChild(listItem);
        }
    }

    // ✅ Função para remover arquivos da lista
    function removeFile(fileName) {
        uploadedFiles = uploadedFiles.filter(file => file.name !== fileName);
        renderFileList();
    }

    // ✅ Atualiza a lista de arquivos no frontend
    function renderFileList() {
        fileList.innerHTML = "";
        uploadedFiles.forEach(file => {
            const listItem = document.createElement("li");
            listItem.innerHTML = `${file.name} 
                <span class="remove-file" onclick="removeFile('${file.name}')">❌</span>`;
            fileList.appendChild(listItem);
        });
    }

    // ✅ Eventos para arrastar e soltar arquivos
    if (dropArea && fileInput && fileList) {
        dropArea.addEventListener("dragover", (event) => {
            event.preventDefault();
            dropArea.classList.add("dragover");
        });

        dropArea.addEventListener("dragleave", () => {
            dropArea.classList.remove("dragover");
        });

        dropArea.addEventListener("drop", (event) => {
            event.preventDefault();
            dropArea.classList.remove("dragover");
            handleFiles(event.dataTransfer.files);
        });

        // Clique para selecionar arquivos
        dropArea.addEventListener("click", () => fileInput.click());

        fileInput.addEventListener("change", () => handleFiles(fileInput.files));
    }

    // ✅ Upload de arquivos via formulário
    if (uploadForm) {
        uploadForm.addEventListener("submit", function (event) {
            event.preventDefault();

            let formData = new FormData();
            uploadedFiles.forEach(file => formData.append("arquivo", file));

            fetch(uploadForm.action, {
                method: "POST",
                headers: {
                    "X-CSRFToken": document.querySelector("input[name=csrfmiddlewaretoken]").value
                },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    alert("📂 Arquivo enviado com sucesso!");
                    uploadedFiles = [];
                    renderFileList();
                } else {
                    alert("⚠️ Erro: " + data.error);
                }
            })
            .catch(error => console.error("❌ Erro no upload:", error));
        });
    }

    // ✅ Função para enviar perguntas ao Assistente Jurídico
    function sendQuestion() {
        let question = chatInput.value.trim();
        if (!question && uploadedFiles.length === 0) return;

        // Exibir a mensagem do usuário no chat
        chatBox.innerHTML += `<div class="chat-bubble user-msg"><strong>Você:</strong> ${question}</div>`;
        chatInput.value = "";

        // Exibir indicador de digitação
        let typingIndicator = document.createElement("div");
        typingIndicator.id = "typing";
        typingIndicator.classList.add("chat-bubble", "bot-msg", "typing-indicator");
        typingIndicator.innerHTML = "<span></span><span></span><span></span>";
        chatBox.appendChild(typingIndicator);
        chatBox.scrollTop = chatBox.scrollHeight;

        // Criar formulário para envio
        let formData = new FormData();
        formData.append("message", question);
        uploadedFiles.forEach(file => formData.append("files", file));

        fetch("/IA/assistente-juridico/ask/", {
            method: "POST",
            headers: {
                "X-CSRFToken": document.querySelector("input[name=csrfmiddlewaretoken]").value
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById("typing").remove(); // Remove indicador de digitação

            // Exibir resposta do chatbot
            let botMessage = document.createElement("div");
            botMessage.classList.add("chat-bubble", "bot-msg");
            botMessage.innerHTML = `<strong>IA:</strong> ${data.response}`;
            chatBox.appendChild(botMessage);
            chatBox.scrollTop = chatBox.scrollHeight;

            uploadedFiles = []; // Limpar arquivos enviados
            renderFileList();
        })
        .catch(error => {
            console.error("❌ Erro ao enviar:", error);
            document.getElementById("typing").remove();
            chatBox.innerHTML += `<div class="chat-bubble bot-msg"><strong>IA:</strong> Erro ao obter resposta. Tente novamente.</div>`;
        });
    }

    // ✅ Ativar envio ao pressionar Enter
    chatInput.addEventListener("keypress", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            sendQuestion();
        }
    });

    // ✅ Tornar a função global para o botão de envio
    if (sendButton) {
        sendButton.addEventListener("click", sendQuestion);
    }
});