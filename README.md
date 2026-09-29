<div align="center">

<img src="./assets/banner.png" alt="Guilherme Araújo, dev fullstack, Java e React. O que acontece depois do clique." width="100%" />

<br/>

[![Portfólio](https://img.shields.io/badge/Portfólio-guilherme--portfolio.dev-15110a?style=flat-square&labelColor=15110a&color=fbe311)](https://guilherme-portfolio.dev)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-guilherme--araújo--de--oliveira-15110a?style=flat-square&labelColor=15110a&color=f2ecdc)](https://www.linkedin.com/in/guilherme-ara%C3%BAjo-de-oliveira)
[![Email](https://img.shields.io/badge/Email-guilherme.workoliveira%40gmail.com-15110a?style=flat-square&labelColor=15110a&color=f2ecdc)](mailto:guilherme.workoliveira@gmail.com)

</div>

## Sobre

Vim do design. Entrei na Lojas Marisa em 2025 e hoje trabalho com UX/UI. Eu entregava a tela e
outra pessoa decidia como o dado ia ser guardado, validado e devolvido. Fui aprender essa parte.

Hoje estudo Ciência da Computação na Anhembi Morumbi (formatura em 2028) e faço as duas pontas:
API em Java e Spring no servidor, React e Next.js na tela. Procuro estágio ou primeira vaga como
dev fullstack, em São Paulo.

O que veio do design eu não larguei: quando desenho uma resposta de erro, penso em quem vai ler
ela às duas da manhã tentando descobrir por que a integração quebrou.

## Três APIs, com teste no CI

| Projeto | O que resolve | Prova |
|---|---|---|
| [**E-commerce API**](https://github.com/Guilhr-07/ecommerce-api) | Catálogo aberto para leitura, escrita só para ADMIN. JWT, BCrypt, upload de imagem, Swagger | 9 endpoints, 15 testes |
| [**Controle Financeiro API**](https://github.com/Guilhr-07/controle-financeiro-api) | Gastos com resumo mensal. O Postgres soma, não o Java, e todo valor é BigDecimal | 2 consultas JPQL agregam no banco, 9 testes |
| [**Gestor de Tarefas API**](https://github.com/Guilhr-07/gestor-tarefas-api) | CRUD com camadas separadas e todo erro no formato da RFC 7807 | 8 testes |

Java 21, Spring Boot 4, Spring Data JPA, PostgreSQL, Flyway, JUnit 5, Docker e
GitHub Actions nas três. Cada README tem a seção "O que ficou de fora".

O case de cada uma, com o que eu escolhi e por quê, está em
[guilherme-portfolio.dev](https://guilherme-portfolio.dev).

## Na tela

- **[guilherme-portfolio.dev](https://guilherme-portfolio.dev):** Next.js, React e TypeScript, feito por mim do layout ao deploy. O console da página reproduz o contrato real das APIs.
- **Lince:** plataforma B2B de inteligência de preço que fiz sozinho. Backend em FastAPI com alerta por SSE, front em React que roda em web, desktop (Tauri) e Android (Capacitor) da mesma base.

## Agora

- **Na fila, até novembro:** a E-commerce API no ar na AWS, com deploy pelo GitHub Actions e OIDC. Depois, Kafka.
- **Ainda não tenho:** API minha rodando em produção, AWS e mensageria. Hoje as três sobem no Docker da minha máquina.
